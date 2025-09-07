# from flask import Blueprint, request
# from app.services.campaign_service import (
#     create_campaign,
#     update_campaign,
#     delete_campaign,
# )
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.utils.authz import require_org_role
from app.models.campaign import (
    list_campaigns,
    create_campaign,
    get_campaign,
    update_campaign,
    delete_campaign,
)
from app.utils.slug import slugify


# campaign = Blueprint('campaign', __name__)
campaigns = Blueprint("campaigns", __name__)

# @campaign.route('/campaigns', methods=['POST'])
# def create():
#     return create_campaign(request.json)

# @campaign.route('/campaigns', methods=['GET'])
# def read():
#     return get_campaigns()

# @campaign.route('/campaigns/<int:id>', methods=['PUT'])
# def update(id):
#     return update_campaign(id, request.json)

# @campaign.route('/campaigns/<int:id>', methods=['DELETE'])
# def delete(id):
#     return delete_campaign(id)


# GET /api/campaigns?org_id=...
@campaigns.get("/api/campaigns")
@require_org_role()  # any member can read
def list_for_org():
    claims = get_jwt()
    org_id = request.args.get("org_id") or claims.get("org_id")
    items = list_campaigns(org_id)
    return jsonify(items), 200


# POST /api/campaigns  { title, goal?, status?, custom_domain?, org_id? }
@campaigns.post("/api/campaigns")
@require_org_role("admin", "owner")
def create():
    body = request.get_json(force=True, silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    org_id = body.get("org_id") or get_jwt().get("org_id")
    goal = float(body.get("goal") or 0)
    status = body.get("status") or "draft"
    custom_domain = body.get("custom_domain") or None
    try:
        camp = create_campaign(
            org_id=org_id,
            title=title,
            goal=goal,
            status=status,
            custom_domain=custom_domain,
        )
        return jsonify(camp), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# PATCH /api/campaigns/<id>  { title?, goal?, status?, slug?, custom_domain? }
@campaigns.patch("/api/campaigns/<campaign_id>")
@jwt_required()  # we'll also assert membership against the campaign's org
def patch(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404

    # role check against the campaign's org
    from app.models.org_user import get_user_role_in_org
    from flask_jwt_extended import get_jwt_identity

    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(silent=True) or {}
    updates = {}
    if "title" in body:
        updates["title"] = (body["title"] or "").strip()
    if "goal" in body:
        updates["goal"] = float(body["goal"])
    if "status" in body:
        updates["status"] = body["status"]
    if "slug" in body:
        updates["slug"] = slugify(body["slug"])
    if "custom_domain" in body:
        updates["custom_domain"] = body["custom_domain"] or None

    try:
        newrow = update_campaign(campaign_id, **updates)
        if newrow is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(newrow), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# DELETE /api/campaigns/<id>
@campaigns.delete("/api/campaigns/<campaign_id>")
@jwt_required()
def delete(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404

    from app.models.org_user import get_user_role_in_org
    from flask_jwt_extended import get_jwt_identity

    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    ok = delete_campaign(campaign_id)
    return ("", 204) if ok else (jsonify({"error": "not found"}), 404)
