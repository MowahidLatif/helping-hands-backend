import os
from flask import Blueprint, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

core = Blueprint("core", __name__)

_STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "static")


@core.get("/campaign-stub")
def campaign_stub():
    """Serve campaign stub UI for E2E testing."""
    return send_from_directory(_STATIC, "campaign_stub.html")


@core.get("/")
def root():
    return jsonify({"service": "donations-api", "ok": True})


@core.get("/api")
def api_index():
    return jsonify(
        {
            "endpoints": {
                "auth": ["/api/auth/login (POST)", "/api/auth/signup (POST)"],
                "users": ["/api/users ..."],
            }
        }
    )


@core.get("/api/me")
@jwt_required()
def me():
    claims = get_jwt()
    return jsonify(
        {
            "user_id": get_jwt_identity(),
            "org_id": claims.get("org_id"),
            "role": claims.get("role"),
        }
    )
