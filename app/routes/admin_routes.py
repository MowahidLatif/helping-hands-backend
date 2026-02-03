from flask import Blueprint, Response
from prometheus_client import REGISTRY, generate_latest, CONTENT_TYPE_LATEST

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/admin/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        generate_latest(REGISTRY),
        mimetype=CONTENT_TYPE_LATEST,
    )
