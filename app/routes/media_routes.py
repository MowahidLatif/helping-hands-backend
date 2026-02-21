from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.campaign import get_campaign
from app.models.media import create_campaign_media, get_media_item, delete_media_item
from app.utils.s3_helpers import (
    make_key,
    presign_put,
    public_url,
    upload_object,
    delete_object,
)
from app.utils.embed import validate_embed_url, embed_url_to_iframe_src
from app.utils.media_validators import (
    validate_content_type,
    validate_filename,
    validate_size,
    infer_media_type_from_filename,
    infer_media_type_from_content_type,
    infer_content_type_from_filename,
)

media_bp = Blueprint("media", __name__)


@media_bp.get("/api/media/signed-url")
@jwt_required()
def signed_url():
    campaign_id = request.args.get("campaign_id")
    filename = (request.args.get("filename") or "").strip()
    content_type = (
        request.args.get("content_type") or ""
    ).strip() or "application/octet-stream"
    mtype = (request.args.get("type") or "other").lower()
    if not campaign_id:
        return jsonify({"error": "campaign_id required"}), 400
    if not filename:
        return jsonify({"error": "filename required"}), 400
    if mtype not in ("image", "video", "doc", "other"):
        return jsonify({"error": "type must be image, video, doc, or other"}), 400

    # Infer media type from filename if generic
    if mtype == "other":
        mtype = (
            infer_media_type_from_filename(filename)
            or infer_media_type_from_content_type(content_type)
            or "other"
        )

    ok, err = validate_filename(filename, mtype)
    if not ok:
        return jsonify({"error": err}), 400
    ok, err = validate_content_type(content_type, mtype)
    if not ok:
        return jsonify({"error": err}), 400
    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({"error": "campaign not found"}), 404

    from app.models.org_user import get_user_role_in_org

    role = get_user_role_in_org(get_jwt_identity(), campaign["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    key = make_key(campaign["org_id"], campaign_id, filename)
    signed = presign_put(key, content_type)
    return jsonify({"key": key, **signed}), 200


@media_bp.post("/api/media/upload")
@jwt_required()
def upload():
    """
    Accept multipart file upload, upload to S3, persist metadata.
    Form fields: file (required), campaign_id (required), description (optional), sort (optional).
    """
    campaign_id = request.form.get("campaign_id", "").strip()
    if not campaign_id:
        return jsonify({"error": "campaign_id required"}), 400

    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({"error": "campaign not found"}), 404

    from app.models.org_user import get_user_role_in_org

    role = get_user_role_in_org(get_jwt_identity(), campaign["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "file required"}), 400

    filename = file.filename.strip()
    content_type = (file.content_type or "").strip() or "application/octet-stream"
    # Browsers sometimes send application/octet-stream for images; infer from extension
    if content_type == "application/octet-stream":
        inferred_ct = infer_content_type_from_filename(filename)
        if inferred_ct:
            content_type = inferred_ct
    mtype = (
        infer_media_type_from_filename(filename)
        or infer_media_type_from_content_type(content_type)
        or "image"
    )
    if mtype not in ("image", "video", "doc"):
        mtype = "image"

    ok, err = validate_filename(filename, mtype)
    if not ok:
        return jsonify({"error": err}), 400
    ok, err = validate_content_type(content_type, mtype)
    if not ok:
        return jsonify({"error": err}), 400

    file_bytes = file.read()
    size_bytes = len(file_bytes)
    ok, err = validate_size(size_bytes, mtype)
    if not ok:
        return jsonify({"error": err}), 400

    key = make_key(campaign["org_id"], campaign_id, filename)
    upload_object(key, file_bytes, content_type)

    sort_val = request.form.get("sort")
    try:
        sort = int(sort_val) if sort_val is not None and sort_val != "" else None
    except (TypeError, ValueError):
        sort = None

    row = create_campaign_media(
        org_id=campaign["org_id"],
        campaign_id=campaign_id,
        type=mtype,
        s3_key=key,
        content_type=content_type,
        size_bytes=size_bytes,
        url=public_url(key),
        description=request.form.get("description") or None,
        sort=sort,
    )
    return jsonify(row), 201


@media_bp.delete("/api/media/<media_id>")
@jwt_required()
def delete_media(media_id):
    """Delete a campaign media item. Removes from DB and S3 (if applicable)."""
    item = get_media_item(media_id)
    if not item:
        return jsonify({"error": "not found"}), 404

    from app.models.org_user import get_user_role_in_org

    role = get_user_role_in_org(get_jwt_identity(), item["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    if item.get("s3_key"):
        try:
            delete_object(item["s3_key"])
        except Exception:
            pass  # Don't block DB deletion if S3 deletion fails

    delete_media_item(media_id)
    return "", 204


@media_bp.post("/api/media")
@jwt_required()
def persist():
    body = request.get_json(force=True, silent=True) or {}
    campaign_id = body.get("campaign_id")
    mtype = (body.get("type") or "image").lower()
    if not campaign_id:
        return jsonify({"error": "campaign_id required"}), 400

    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({"error": "campaign not found"}), 404

    from app.models.org_user import get_user_role_in_org

    role = get_user_role_in_org(get_jwt_identity(), campaign["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    if mtype == "embed":
        url = (body.get("url") or "").strip()
        if not url:
            return jsonify({"error": "url required for embed type"}), 400
        ok, err = validate_embed_url(url)
        if not ok:
            return jsonify({"error": err}), 400
        iframe_src = embed_url_to_iframe_src(url)
        row = create_campaign_media(
            org_id=campaign["org_id"],
            campaign_id=campaign_id,
            type="embed",
            s3_key=None,
            content_type="text/html",
            size_bytes=None,
            url=iframe_src or url,
            description=body.get("description"),
            sort=body.get("sort"),
        )
    else:
        key = body.get("key")
        if not key:
            return (
                jsonify(
                    {
                        "error": "key required for uploads (use type=embed for YouTube/Vimeo)"
                    }
                ),
                400,
            )
        if mtype not in ("image", "video", "doc", "other"):
            return jsonify({"error": "invalid type"}), 400
        # Validate key format and filename (key is org/campaign/uuid-filename.ext)
        key_filename = key.split("/")[-1] if "/" in key else key
        ok, err = validate_filename(key_filename, mtype)
        if not ok:
            return jsonify({"error": err}), 400
        ct = body.get("content_type")
        ok, err = validate_content_type(ct, mtype)
        if not ok:
            return jsonify({"error": err}), 400
        size_bytes = body.get("size_bytes")
        if size_bytes is not None:
            try:
                size_bytes = int(size_bytes)
            except (TypeError, ValueError):
                return jsonify({"error": "size_bytes must be an integer"}), 400
            ok, err = validate_size(size_bytes, mtype)
            if not ok:
                return jsonify({"error": err}), 400
        else:
            size_bytes = None
        row = create_campaign_media(
            org_id=campaign["org_id"],
            campaign_id=campaign_id,
            type=mtype,
            s3_key=key,
            content_type=ct,
            size_bytes=size_bytes,
            url=public_url(key),
            description=body.get("description"),
            sort=body.get("sort"),
        )
    return jsonify(row), 201
