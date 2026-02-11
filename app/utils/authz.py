from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from app.models.org_user import get_user_role_in_org


def require_org_role(*allowed):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Debug: Check if Authorization header exists
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                print(f"[authz] No Authorization header for {request.path}")
                return jsonify({"error": "Missing Authorization header"}), 401

            try:
                verify_jwt_in_request()
            except Exception as e:
                print(f"[authz] JWT verification failed: {str(e)}")
                return jsonify({"error": "Invalid token", "details": str(e)}), 401

            user_id = get_jwt_identity()
            jwt_claims = get_jwt()

            print(f"[authz] user_id={user_id}, claims={jwt_claims}")

            body = request.get_json(silent=True) or {}
            org_id = (
                kwargs.get("org_id")
                or request.args.get("org_id")
                or body.get("org_id")
                or jwt_claims.get("org_id")
            )
            if not org_id:
                print("[authz] No org_id found in request or claims")
                return jsonify({"error": "org_id required"}), 400

            role = get_user_role_in_org(user_id, org_id)
            print(f"[authz] org_id={org_id}, role={role}")
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
