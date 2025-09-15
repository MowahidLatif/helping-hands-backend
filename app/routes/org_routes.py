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

orgs = Blueprint("orgs", __name__)


# Create an org (caller becomes owner)
@orgs.post("/api/orgs")
@jwt_required()
def create_org():
    user_id = get_jwt_identity()
    name = (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    org = create_organization(name)
    add_user_to_org(org["id"], user_id, role="owner")
    return jsonify(org), 201


# List orgs current user belongs to
@orgs.get("/api/orgs")
@jwt_required()
def my_orgs():
    user_id = get_jwt_identity()
    return jsonify(list_user_organizations(user_id)), 200


# Get org by id (must be a member)
@orgs.get("/api/orgs/<org_id>")
@require_org_role()  # any member
def get_org(org_id):
    org = get_organization(org_id)
    if not org:
        return jsonify({"error": "not found"}), 404
    return jsonify(org), 200


# Update org name (admin/owner)
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


# Delete org (owner only)
@orgs.delete("/api/orgs/<org_id>")
@require_org_role("owner")
def delete_org(org_id):
    ok = delete_organization(org_id)
    return ("", 204) if ok else (jsonify({"error": "not found"}), 404)


# Members: list
@orgs.get("/api/orgs/<org_id>/members")
@require_org_role("admin", "owner")
def members(org_id):
    return jsonify(list_org_members(org_id)), 200


# Members: add by email with role (admin/owner)
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


# Members: change role (admin/owner)
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


# Members: remove (admin/owner)
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
