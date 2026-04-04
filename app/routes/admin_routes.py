import os
from flask import Blueprint, Response, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from prometheus_client import REGISTRY, generate_latest, CONTENT_TYPE_LATEST

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/admin/metrics")
@jwt_required()
def metrics():
    """Prometheus metrics endpoint. Requires privileged JWT role."""
    allowed_roles = {
        role.strip().lower()
        for role in (os.getenv("ADMIN_METRICS_ALLOWED_ROLES", "owner,admin").split(","))
        if role.strip()
    }
    role = (get_jwt().get("role") or "").strip().lower()
    if role not in allowed_roles:
        return jsonify({"error": "forbidden"}), 403
    return Response(
        generate_latest(REGISTRY),
        mimetype=CONTENT_TYPE_LATEST,
    )
