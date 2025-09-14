# from flask import Blueprint, request
# from app.services.media_service import (
#     add_media, get_media_by_campaign
# )

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.campaign import get_campaign
from app.models.media import create_campaign_media
from app.utils.s3_helpers import make_key, presign_put, public_url

media_bp = Blueprint("media", __name__)


# GET /api/media/signed-url?campaign_id=...&filename=...&content_type=...
@media_bp.get("/api/media/signed-url")
@jwt_required()
def signed_url():
    campaign_id = request.args.get("campaign_id")
    filename = request.args.get("filename") or "upload.bin"
    content_type = request.args.get("content_type") or "application/octet-stream"
    if not campaign_id:
        return jsonify({"error": "campaign_id required"}), 400

    # role check: admin/owner on the campaign's org
    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({"error": "campaign not found"}), 404

    from app.models.org_user import get_user_role_in_org

    role = get_user_role_in_org(get_jwt_identity(), campaign["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    key = make_key(campaign["org_id"], campaign_id, filename)
    signed = presign_put(key, content_type)
    # include key so the client can POST metadata later
    return jsonify({"key": key, **signed}), 200


# POST /api/media  (persist metadata after successful upload)
# body: { campaign_id, key, type, content_type?, size_bytes?, description?, sort? }
@media_bp.post("/api/media")
@jwt_required()
def persist():
    body = request.get_json(force=True, silent=True) or {}
    campaign_id = body.get("campaign_id")
    key = body.get("key")
    mtype = (body.get("type") or "image").lower()
    if not campaign_id or not key:
        return jsonify({"error": "campaign_id and key are required"}), 400
    if mtype not in ("image", "video", "doc", "other"):
        return jsonify({"error": "invalid type"}), 400

    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({"error": "campaign not found"}), 404

    from app.models.org_user import get_user_role_in_org

    role = get_user_role_in_org(get_jwt_identity(), campaign["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    row = create_campaign_media(
        org_id=campaign["org_id"],
        campaign_id=campaign_id,
        type=mtype,
        s3_key=key,
        content_type=body.get("content_type"),
        size_bytes=(
            int(body["size_bytes"]) if body.get("size_bytes") is not None else None
        ),
        url=public_url(key),  # dev convenience (bucket is public in dev)
        description=body.get("description"),
        sort=body.get("sort"),
    )
    return jsonify(row), 201
