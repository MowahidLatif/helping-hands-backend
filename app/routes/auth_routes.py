from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    create_access_token,
)
from app.services.auth_service import (
    login_user,
    signup_user,
    change_password,
    delete_account,
    setup_2fa,
    verify_2fa,
    disable_2fa,
    confirm_2fa_login,
)
from app.utils.rate_limit import rate_limit_decorator

auth_bp = Blueprint("auth", __name__)
_auth_limit = int(__import__("os").getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))


def _reject_pre_2fa():
    """Return 401 if current JWT is a pre_2fa token (must complete 2FA first)."""
    if get_jwt().get("pre_2fa"):
        return jsonify({"error": "Complete 2FA first"}), 401
    return None


@auth_bp.post("/register")
@rate_limit_decorator(_auth_limit, "auth")
def register():
    data = request.get_json(force=True, silent=True) or {}
    resp = signup_user(data)
    return jsonify(resp), (201 if "access_token" in resp else 400)


@auth_bp.post("/login")
@rate_limit_decorator(_auth_limit, "auth")
def login():
    data = request.get_json(force=True, silent=True) or {}
    resp = login_user(data)
    if "error" in resp:
        return jsonify(resp), 401
    return jsonify(resp), 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    new_access = create_access_token(identity=user_id)
    return jsonify({"access_token": new_access}), 200


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.json
    response = signup_user(data)
    return jsonify(response), (201 if "id" in response else 400)


@auth_bp.post("/change-password")
@jwt_required()
def change_password_route():
    err = _reject_pre_2fa()
    if err is not None:
        return err
    data = request.get_json(force=True, silent=True) or {}
    current = (data.get("current_password") or "").strip()
    new_pw = (data.get("new_password") or "").strip()
    if not current or not new_pw:
        return jsonify({"error": "current_password and new_password required"}), 400
    result = change_password(get_jwt_identity(), current, new_pw)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 200


@auth_bp.post("/delete-account")
@jwt_required()
def delete_account_route():
    """Anonymize current user (no hard delete). Requires password; 2FA code if enabled."""
    err = _reject_pre_2fa()
    if err is not None:
        return err
    data = request.get_json(force=True, silent=True) or {}
    password = (data.get("password") or "").strip()
    if not password:
        return jsonify({"error": "password is required"}), 400
    code = (data.get("code") or "").strip() or None
    result = delete_account(get_jwt_identity(), password, totp_code=code)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 200


@auth_bp.post("/2fa/setup")
@jwt_required()
def twofa_setup():
    err = _reject_pre_2fa()
    if err is not None:
        return err
    result = setup_2fa(get_jwt_identity())
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 200


@auth_bp.post("/2fa/verify")
@jwt_required()
def twofa_verify():
    err = _reject_pre_2fa()
    if err is not None:
        return err
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("code") or "").strip()
    result = verify_2fa(get_jwt_identity(), code)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 200


@auth_bp.post("/2fa/disable")
@jwt_required()
def twofa_disable():
    err = _reject_pre_2fa()
    if err is not None:
        return err
    data = request.get_json(force=True, silent=True) or {}
    password = (data.get("password") or "").strip()
    code = (data.get("code") or "").strip()
    if not password or not code:
        return jsonify({"error": "password and code required"}), 400
    result = disable_2fa(get_jwt_identity(), password, code)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 200


@auth_bp.post("/2fa/confirm-login")
def twofa_confirm_login():
    """Exchange temp_token + TOTP code for real access and refresh tokens. No Bearer required for temp_token in body."""
    data = request.get_json(force=True, silent=True) or {}
    temp_token = (data.get("temp_token") or "").strip()
    code = (data.get("code") or "").strip()
    if not temp_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            temp_token = auth_header[7:].strip()
    if not temp_token or not code:
        return jsonify({"error": "temp_token and code required"}), 400
    result = confirm_2fa_login(temp_token, code)
    if "error" in result:
        return jsonify({"error": result["error"]}), 401
    return jsonify(result), 200
