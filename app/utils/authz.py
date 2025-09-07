from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from app.models.org_user import get_user_role_in_org


def require_org_role(*allowed):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            jwt_claims = get_jwt()

            body = request.get_json(silent=True) or {}
            org_id = (
                kwargs.get("org_id")
                or request.args.get("org_id")
                or body.get("org_id")
                or jwt_claims.get("org_id")
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
