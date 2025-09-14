# from app.services.campaign_service import (
#     create_campaign,
#     update_campaign,
#     delete_campaign,
# )
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt
from app.utils.authz import require_org_role
from app.models.campaign import (
    list_campaigns,
    create_campaign,
    get_campaign,
    update_campaign,
    delete_campaign,
    get_goal_and_total,
    list_giveaway_logs,
)
from app.utils.slug import slugify
import json
from app.utils.cache import r
from app.models.donation import count_and_last_succeeded, recent_succeeded_for_campaign
from app.models.media import list_media_for_campaign
from app.services.giveaway_service import draw_winner_for_campaign
from uuid import UUID
from app.models.org_user import get_user_role_in_org
from flask_jwt_extended import get_jwt_identity
from app.models.donation import select_donations_by_campaign

campaigns = Blueprint("campaigns", __name__)


def _is_uuid(v: str) -> bool:
    try:
        UUID(v)
        return True
    except Exception:
        return False


# GET /api/campaigns?org_id=...
@campaigns.get("/")
@require_org_role()
def list_for_org():
    claims = get_jwt()
    org_id = request.args.get("org_id") or claims.get("org_id")
    items = list_campaigns(org_id)
    return jsonify(items), 200


# POST /api/campaigns  { title, goal?, status?, custom_domain?, org_id? }
@campaigns.post("/")
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
@campaigns.patch("/<campaign_id>")
@jwt_required()  # we'll also assert membership against the campaign's org
def patch(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404

    # role check against the campaign's org
    # from app.models.org_user import get_user_role_in_org
    # from flask_jwt_extended import get_jwt_identity

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
@campaigns.delete("/<campaign_id>")
@jwt_required()
def delete(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404

    # from app.models.org_user import get_user_role_in_org
    # from flask_jwt_extended import get_jwt_identity

    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    ok = delete_campaign(campaign_id)
    return ("", 204) if ok else (jsonify({"error": "not found"}), 404)


@campaigns.get("/<campaign_id>/progress")
def campaign_progress(campaign_id):
    if not _is_uuid(campaign_id):
        return jsonify({"error": "invalid campaign_id"}), 400
    key = f"campaign:{campaign_id}:progress:v1"
    cached = r().get(key)
    if cached:
        return jsonify(json.loads(cached)), 200

    vals = get_goal_and_total(campaign_id)
    if not vals:
        return jsonify({"error": "campaign not found"}), 404
    goal, total = vals
    count, last_dt = count_and_last_succeeded(campaign_id)

    percent = 0.0
    if goal > 0:
        percent = round(min(100.0, (total / goal) * 100.0), 2)

    resp = {
        "campaign_id": campaign_id,
        "goal": goal,
        "total_raised": total,
        "percent": percent,
        "donations_count": count,
        "last_donation_at": last_dt,
    }
    r().setex(key, 30, json.dumps(resp, default=str))
    return jsonify(resp), 200


@campaigns.get("/<campaign_id>/media")
def campaign_media(campaign_id):
    if not _is_uuid(campaign_id):
        return jsonify({"error": "invalid campaign_id"}), 400
    items = list_media_for_campaign(campaign_id)
    return jsonify(items), 200


@campaigns.post("/<campaign_id>/draw-winner")
@jwt_required()
def draw_winner_route(campaign_id):
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "per_donation")
    min_amount_cents = int(body.get("min_amount_cents", 0) or 0)
    notes = body.get("notes")

    claims = get_jwt()
    user_id = claims.get("sub")

    status, payload = draw_winner_for_campaign(
        campaign_id=campaign_id,
        current_user_id=user_id,
        mode=mode,
        min_amount_cents=min_amount_cents,
        notes=notes,
    )
    return jsonify(payload), status


@campaigns.get("/<campaign_id>/giveaway-logs")
@jwt_required()
def get_giveaway_logs(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404
    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403
    limit = int(request.args.get("limit", 20))
    return jsonify(list_giveaway_logs(campaign_id, limit=limit)), 200


@campaigns.get("/<campaign_id>/donations/recent")
def recent_donations(campaign_id):
    if not _is_uuid(campaign_id):
        return jsonify({"error": "invalid campaign_id"}), 400
    limit = int(request.args.get("limit", 10))
    return jsonify(recent_succeeded_for_campaign(campaign_id, limit)), 200


@campaigns.get("/<campaign_id>/donations/export.csv")
@jwt_required()
def export_donations_csv(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404

    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403

    # Build CSV
    rows = select_donations_by_campaign(campaign_id)
    # If your select returns full rows, map them—otherwise write a tighter query that returns only needed fields.
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "donation_id",
            "amount_cents",
            "currency",
            "donor_email",
            "status",
            "created_at",
        ]
    )
    for row in rows:
        # adapt to your tuple/dict shape
        # Example if using dicts:
        # w.writerow([r["id"], r["amount_cents"], r["currency"], r["donor_email"], r["status"], r["created_at"]])
        w.writerow(
            [
                row[0],
                row[4] * 100 if row[4] else None,
                "cad",
                row[3],
                "succeeded",
                row[-1],
            ]
        )  # adjust to your schema!
    out = buf.getvalue()
    return Response(
        out,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="campaign_{campaign_id}_donations.csv"'
        },
    )


@campaigns.get("/<campaign_id>/webhooks/stripe-events")
@jwt_required()
def list_stripe_events(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404
    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403

    from app.utils.db import get_db_connection

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT event_id, type, created_at FROM stripe_events ORDER BY created_at DESC LIMIT 50"
        )
        rows = cur.fetchall()
        return (
            jsonify(
                [{"event_id": r[0], "type": r[1], "created_at": r[2]} for r in rows]
            ),
            200,
        )
