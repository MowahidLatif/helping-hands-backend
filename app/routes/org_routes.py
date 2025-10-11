from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.authz import require_org_role
from app.models.org import (
    create_organization,
    list_user_organizations,
    get_organization,
    update_organization_name,
    delete_organization,
)
from app.models.org_user import (
    add_user_to_org,
    list_org_members,
    set_user_role,
    remove_user_from_org,
    get_user_role_in_org,
)
from app.models.user import get_user_by_email
from app.models.org_email_settings import get_email_settings, upsert_email_settings
from app.utils.db import get_db_connection
from app.utils.slug import slugify_with_fallback
from psycopg2.errors import UniqueViolation

orgs = Blueprint("orgs", __name__)


@orgs.post("/api/orgs")
@jwt_required()
def create_org():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    sub = (data.get("subdomain") or "").strip() or None
    if not name:
        return jsonify({"error": "name required"}), 400
    try:
        org = create_organization(name, sub)
    except UniqueViolation:
        return jsonify({"error": "subdomain already taken"}), 409
    add_user_to_org(org["id"], user_id, role="owner")
    return org, 201


@orgs.get("/api/orgs")
@jwt_required()
def my_orgs():
    user_id = get_jwt_identity()
    return jsonify(list_user_organizations(user_id)), 200


@orgs.get("/api/orgs/<org_id>")
@require_org_role()
def get_org(org_id):
    org = get_organization(org_id)
    if not org:
        return jsonify({"error": "not found"}), 404
    return jsonify(org), 200


@orgs.patch("/api/orgs/<org_id>")
@require_org_role("admin", "owner")
def rename_org(org_id):
    name = (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    org = update_organization_name(org_id, name)
    if not org:
        return jsonify({"error": "not found"}), 404
    return jsonify(org), 200


@orgs.delete("/api/orgs/<org_id>")
@require_org_role("owner")
def delete_org(org_id):
    ok = delete_organization(org_id)
    return ("", 204) if ok else (jsonify({"error": "not found"}), 404)


@orgs.get("/api/orgs/<org_id>/members")
@require_org_role("admin", "owner")
def members(org_id):
    return jsonify(list_org_members(org_id)), 200


@orgs.post("/api/orgs/<org_id>/members")
@require_org_role("admin", "owner")
def add_member(org_id):
    email = (request.json or {}).get("email", "").strip().lower()
    role = (request.json or {}).get("role", "member")
    user = get_user_by_email(email)
    if not user:
        return jsonify({"error": "user not found"}), 404
    add_user_to_org(org_id, user["id"], role=role)
    return jsonify({"added": user["id"], "role": role}), 201


@orgs.patch("/api/orgs/<org_id>/members/<user_id>")
@require_org_role("admin", "owner")
def change_role(org_id, user_id):
    role = (request.json or {}).get("role")
    if role not in ("owner", "admin", "member"):
        return jsonify({"error": "invalid role"}), 400
    ok = set_user_role(org_id, user_id, role)
    return (
        (jsonify({"role": role}), 200) if ok else (jsonify({"error": "not found"}), 404)
    )


@orgs.delete("/api/orgs/<org_id>/members/<user_id>")
@require_org_role("admin", "owner")
def remove_member(org_id, user_id):
    ok = remove_user_from_org(org_id, user_id)
    return ("", 204) if ok else (jsonify({"error": "not found"}), 404)


@orgs.get("/api/orgs/<org_id>/email-settings")
@jwt_required()
def get_org_email_settings(org_id):
    user_id = get_jwt_identity()
    role = get_user_role_in_org(user_id, org_id)
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(get_email_settings(org_id) or {"org_id": org_id})


@orgs.patch("/api/orgs/<org_id>/email-settings")
@jwt_required()
def patch_org_email_settings(org_id):
    user_id = get_jwt_identity()
    role = get_user_role_in_org(user_id, org_id)
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(force=True, silent=True) or {}
    updated = upsert_email_settings(org_id, **payload)
    return jsonify(updated)


@orgs.patch("/api/orgs/<org_id>/subdomain")
@jwt_required()
def set_org_subdomain(org_id):
    user_id = get_jwt_identity()
    role = get_user_role_in_org(user_id, org_id)
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(silent=True) or {}
    sub = slugify_with_fallback(body.get("subdomain"), f"org-{org_id}")

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM organizations WHERE subdomain=%s AND id<>%s",
            (sub, org_id),
        )
        if cur.fetchone():
            return jsonify({"error": "subdomain already in use"}), 409

        cur.execute(
            "UPDATE organizations SET subdomain=%s WHERE id=%s RETURNING id, name, subdomain",
            (sub, org_id),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404

    return jsonify({"id": row[0], "name": row[1], "subdomain": row[2]}), 200
