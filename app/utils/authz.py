from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models.org_user import get_user_role_in_org


def require_org_role(*allowed):
    """Use on routes with <org_id> in the path (or JSON body for POST)."""

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            org_id = kwargs.get("org_id") or (request.get_json(silent=True) or {}).get(
                "org_id"
            )
            if not org_id:
                return jsonify({"error": "org_id required"}), 400
            role = get_user_role_in_org(user_id, org_id)
            if role is None:
                return jsonify({"error": "not a member"}), 403
            if allowed and role not in allowed:
                return (
                    jsonify({"error": "forbidden", "required": allowed, "have": role}),
                    403,
                )
            return fn(*args, **kwargs)

        return wrapper

    return deco
