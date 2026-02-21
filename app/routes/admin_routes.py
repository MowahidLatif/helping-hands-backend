from flask import Blueprint, Response
from flask_jwt_extended import jwt_required
from prometheus_client import REGISTRY, generate_latest, CONTENT_TYPE_LATEST

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/admin/metrics")
@jwt_required()
def metrics():
    """Prometheus metrics endpoint. Requires a valid platform JWT."""
    return Response(
        generate_latest(REGISTRY),
        mimetype=CONTENT_TYPE_LATEST,
    )
