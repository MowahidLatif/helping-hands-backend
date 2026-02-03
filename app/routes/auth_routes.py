from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from app.services.auth_service import login_user, signup_user
from app.utils.rate_limit import rate_limit_decorator

auth_bp = Blueprint("auth", __name__)
_auth_limit = int(__import__("os").getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))


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
    return jsonify(resp), (200 if "access_token" in resp else 401)


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
