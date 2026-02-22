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
from app.models.user import get_user_by_email, create_user as model_create_user
from app.models.org_permissions import (
    get_all_members_permissions,
    set_member_permissions,
    ALL_PERMISSIONS,
)
from app.models.task_status import (
    list_task_statuses,
    create_task_status,
    update_task_status,
    delete_task_status,
    status_in_use_by_tasks,
)
from app.models.org_email_settings import get_email_settings, upsert_email_settings
from app.services.auth_service import _hash_password
import re

from app.utils.db import get_db_connection
from app.utils.slug import slugify_with_fallback
from psycopg2.errors import UniqueViolation

EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
orgs = Blueprint("orgs", __name__)


@orgs.post("/api/orgs")
@jwt_required()
def create_org():
    user_id = get_jwt_identity()
    existing = list_user_organizations(user_id)
    if existing:
        return (
            jsonify(
                {
                    "error": "You already belong to an organization. Create a new account to start a second organization."
                }
            ),
            409,
        )
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
    members_list = list_org_members(org_id)
    perms_map = get_all_members_permissions(org_id)
    for m in members_list:
        m["permissions"] = perms_map.get(m["id"], [])
    return jsonify(members_list), 200


@orgs.post("/api/orgs/<org_id>/members/create")
@require_org_role("admin", "owner")
def create_member(org_id):
    """Create a new user and add to org with optional permissions. Body: email, password, name, permissions[]."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    name = (data.get("name") or "").strip() or None
    permissions = data.get("permissions") or []
    if not email:
        return jsonify({"error": "email required"}), 400
    if not password:
        return jsonify({"error": "password required"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "invalid email format"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    if get_user_by_email(email):
        return jsonify({"error": "email already registered"}), 409
    password_hash = _hash_password(password)
    user = model_create_user(email=email, password_hash=password_hash, name=name)
    add_user_to_org(org_id, user["id"], role="member")
    valid_perms = [p for p in permissions if p in ALL_PERMISSIONS]
    if valid_perms:
        set_member_permissions(org_id, user["id"], valid_perms)
    member_out = {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "role": "member",
        "permissions": valid_perms,
    }
    return jsonify(member_out), 201


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


@orgs.put("/api/orgs/<org_id>/members/<user_id>/permissions")
@require_org_role("admin", "owner")
def update_member_permissions(org_id, user_id):
    """Replace member's permissions. Body: { permissions: string[] }."""
    data = request.get_json(silent=True) or {}
    permissions = data.get("permissions")
    if permissions is None:
        return jsonify({"error": "permissions required"}), 400
    if not isinstance(permissions, list):
        return jsonify({"error": "permissions must be an array"}), 400
    role = get_user_role_in_org(user_id, org_id)
    if not role:
        return jsonify({"error": "user not a member"}), 404
    set_member_permissions(org_id, user_id, permissions)
    return (
        jsonify({"permissions": [p for p in permissions if p in ALL_PERMISSIONS]}),
        200,
    )


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


@orgs.get("/api/orgs/<org_id>/task-statuses")
@require_org_role()
def list_org_task_statuses(org_id):
    return jsonify(list_task_statuses(org_id)), 200


@orgs.post("/api/orgs/<org_id>/task-statuses")
@require_org_role("admin", "owner")
def create_org_task_status(org_id):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    sort_order = data.get("sort_order", 0)
    try:
        sort_order = int(sort_order)
    except (TypeError, ValueError):
        sort_order = 0
    status = create_task_status(org_id, name, sort_order)
    return jsonify(status), 201


@orgs.patch("/api/orgs/<org_id>/task-statuses/<status_id>")
@require_org_role("admin", "owner")
def patch_org_task_status(org_id, status_id):
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if name is not None:
        name = (name or "").strip()
    sort_order = data.get("sort_order")
    if sort_order is not None:
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            sort_order = None
    status = update_task_status(status_id, org_id, name=name, sort_order=sort_order)
    if not status:
        return jsonify({"error": "not found"}), 404
    return jsonify(status), 200


@orgs.delete("/api/orgs/<org_id>/task-statuses/<status_id>")
@require_org_role("admin", "owner")
def delete_org_task_status(org_id, status_id):
    if status_in_use_by_tasks(status_id):
        return jsonify({"error": "status is in use by tasks"}), 400
    if not delete_task_status(status_id, org_id):
        return jsonify({"error": "not found"}), 404
    return "", 204


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
