from flask import Blueprint, jsonify

core = Blueprint("core", __name__)


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
