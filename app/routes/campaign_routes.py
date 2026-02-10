from app.utils.db import get_db_connection
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt
from app.utils.authz import require_org_role
from app.models.campaign import (
    list_campaigns,
    create_campaign,
    get_campaign,
    update_campaign,
    delete_campaign,
    list_giveaway_logs,
)
from app.utils.slug import slugify
from app.utils.domain import validate_custom_domain
import json
from app.utils.cache import r
from app.models.donation import (
    count_and_last_succeeded,
    recent_succeeded_for_campaign,
    select_donations_by_campaign,
)
from app.models.media import list_media_for_campaign
from app.services.giveaway_service import draw_winner_for_campaign
from uuid import UUID
from app.models.org_user import get_user_role_in_org
from flask_jwt_extended import get_jwt_identity
from app.models.email_receipt import (
    list_receipts_for_campaign,
    get_receipt,
    resend_receipt,
    render_receipt_content,
)
from app.models.campaign_comment import (
    create_comment,
    get_comment,
    list_comments,
    update_comment,
    delete_comment,
)
from app.models.campaign_update import (
    create_update,
    get_update,
    list_updates,
    update_update,
    delete_update,
)
from app.tasks import enqueue_campaign_update_notifications
import csv
import io

campaigns = Blueprint("campaigns", __name__)


def _is_uuid(v: str) -> bool:
    try:
        UUID(v)
        return True
    except Exception:
        return False


@campaigns.get("/")
@require_org_role()
def list_for_org():
    claims = get_jwt()
    org_id = request.args.get("org_id") or claims.get("org_id")
    status = request.args.get("status")  # e.g. ?status=active or ?status=completed
    items = list_campaigns(org_id, status=status)
    return jsonify(items), 200


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
    custom_domain = (body.get("custom_domain") or "").strip() or None
    giveaway_prize_cents = body.get("giveaway_prize_cents")
    if giveaway_prize_cents is not None:
        try:
            giveaway_prize_cents = int(giveaway_prize_cents)
            if giveaway_prize_cents < 0:
                giveaway_prize_cents = None
        except (TypeError, ValueError):
            giveaway_prize_cents = None
    if custom_domain:
        ok, err = validate_custom_domain(custom_domain)
        if not ok:
            return jsonify({"error": err}), 400
    try:
        camp = create_campaign(
            org_id=org_id,
            title=title,
            goal=goal,
            status=status,
            custom_domain=custom_domain,
            giveaway_prize_cents=giveaway_prize_cents,
        )
        return jsonify(camp), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@campaigns.patch("/<campaign_id>")
@jwt_required()
def patch(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404

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
        val = (body["custom_domain"] or "").strip() or None
        if val:
            ok, err = validate_custom_domain(val)
            if not ok:
                return jsonify({"error": err}), 400
        updates["custom_domain"] = val
    if "giveaway_prize_cents" in body:
        val = body["giveaway_prize_cents"]
        if val is None:
            updates["giveaway_prize_cents"] = None
        else:
            try:
                updates["giveaway_prize_cents"] = max(0, int(val))
            except (TypeError, ValueError):
                return (
                    jsonify(
                        {"error": "giveaway_prize_cents must be a non-negative integer"}
                    ),
                    400,
                )

    try:
        newrow = update_campaign(campaign_id, **updates)
        if newrow is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(newrow), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@campaigns.delete("/<campaign_id>")
@jwt_required()
def delete(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404

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

    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404
    goal = float(camp.get("goal", 0))
    total = float(camp.get("total_raised", 0))
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
    fee_cents = camp.get("platform_fee_cents")
    if fee_cents is not None:
        resp["platform_fee_cents"] = fee_cents
        resp["platform_fee_percent"] = float(camp.get("platform_fee_percent") or 0)
        resp["net_to_org_cents"] = int(total * 100) - int(fee_cents)
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

    rows = select_donations_by_campaign(campaign_id)

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
        w.writerow(
            [
                row[0],
                row[4] * 100 if row[4] else None,
                "cad",
                row[3],
                "succeeded",
                row[-1],
            ]
        )
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


@campaigns.get("/<campaign_id>/receipts")
@jwt_required()
def campaign_receipts(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404
    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    try:
        limit = int(request.args.get("limit", 50))
    except Exception:
        limit = 50

    items = list_receipts_for_campaign(campaign_id, limit=limit)
    return jsonify(items), 200


@campaigns.get("/<campaign_id>/receipts/<receipt_id>/preview")
@jwt_required()
def campaign_receipt_preview(campaign_id, receipt_id):
    rec = get_receipt(receipt_id)
    if not rec or rec["campaign_id"] != campaign_id:
        return jsonify({"error": "not found"}), 404
    role = get_user_role_in_org(get_jwt_identity(), rec["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    html = rec.get("body_html") or "<p>No content</p>"
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@campaigns.post("/<campaign_id>/receipts/<receipt_id>/resend")
@jwt_required()
def campaign_receipt_resend(campaign_id, receipt_id):
    rec = get_receipt(receipt_id)
    if not rec or rec["campaign_id"] != campaign_id:
        return jsonify({"error": "not found"}), 404
    role = get_user_role_in_org(get_jwt_identity(), rec["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "forbidden"}), 403

    newrow = resend_receipt(receipt_id)
    if not newrow:
        return jsonify({"error": "not found"}), 404
    return jsonify(newrow), 201


@campaigns.get("/<campaign_id>/receipts/preview-template")
@jwt_required()
def preview_receipt_template(campaign_id: str):
    """
    Render the org's current email templates (subject/text/html) for a fake donation
    without creating any DB rows.
    Query params: amount_cents, currency, donor_email
    """
    amount_cents = int(request.args.get("amount_cents", "2500") or 2500)
    currency = (request.args.get("currency") or "cad").lower()
    donor_email = request.args.get("donor_email") or "demo@example.com"

    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404

    d = {
        "id": None,
        "org_id": camp["org_id"],
        "campaign_id": campaign_id,
        "campaign_title": camp["title"],
        "amount_cents": amount_cents,
        "currency": currency,
        "donor_email": donor_email,
    }

    content = render_receipt_content(camp["org_id"], d)
    return (
        jsonify(
            {
                "subject": content["subject"],
                "body_text": content["body_text"],
                "body_html": content["body_html"],
            }
        ),
        200,
    )


@campaigns.get("/<campaign_id>")
@jwt_required()
def get_one(campaign_id):
    row = get_campaign(campaign_id)
    return (jsonify(row), 200) if row else ({"error": "not found"}, 404)


# --- Comments ---


@campaigns.get("/<campaign_id>/comments")
def list_comments_route(campaign_id):
    if not _is_uuid(campaign_id):
        return jsonify({"error": "invalid campaign_id"}), 400
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404
    limit = min(int(request.args.get("limit", 50) or 50), 100)
    after = request.args.get("after")
    items = list_comments(campaign_id, limit=limit, after=after)
    return jsonify(items), 200


@campaigns.post("/<campaign_id>/comments")
@jwt_required()
def create_comment_route(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404
    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if not role:
        return jsonify({"error": "must be org member to comment"}), 403
    body = (request.get_json(silent=True) or {}).get("body", "")
    if not body.strip():
        return jsonify({"error": "body required"}), 400
    comment = create_comment(campaign_id, get_jwt_identity(), body.strip())
    return jsonify(comment), 201


@campaigns.get("/<campaign_id>/comments/<comment_id>")
def get_comment_route(campaign_id, comment_id):
    comment = get_comment(comment_id)
    if not comment or str(comment["campaign_id"]) != campaign_id:
        return jsonify({"error": "not found"}), 404
    return jsonify(comment), 200


@campaigns.patch("/<campaign_id>/comments/<comment_id>")
@jwt_required()
def patch_comment_route(campaign_id, comment_id):
    comment = get_comment(comment_id)
    if not comment or str(comment["campaign_id"]) != campaign_id:
        return jsonify({"error": "not found"}), 404
    if str(comment["user_id"]) != get_jwt_identity():
        return jsonify({"error": "forbidden"}), 403
    body = (request.get_json(silent=True) or {}).get("body")
    if body is None:
        return jsonify({"error": "body required"}), 400
    updated = update_comment(comment_id, get_jwt_identity(), body.strip())
    return jsonify(updated), 200


@campaigns.delete("/<campaign_id>/comments/<comment_id>")
@jwt_required()
def delete_comment_route(campaign_id, comment_id):
    comment = get_comment(comment_id)
    if not comment or str(comment["campaign_id"]) != campaign_id:
        return jsonify({"error": "not found"}), 404
    if str(comment["user_id"]) != get_jwt_identity():
        return jsonify({"error": "forbidden"}), 403
    ok = delete_comment(comment_id, get_jwt_identity())
    return ("", 204) if ok else (jsonify({"error": "not found"}), 404)


# --- Updates ---


@campaigns.get("/<campaign_id>/updates")
def list_updates_route(campaign_id):
    if not _is_uuid(campaign_id):
        return jsonify({"error": "invalid campaign_id"}), 400
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404
    limit = min(int(request.args.get("limit", 50) or 50), 100)
    after = request.args.get("after")
    items = list_updates(campaign_id, limit=limit, after=after)
    return jsonify(items), 200


@campaigns.post("/<campaign_id>/updates")
@jwt_required()
def create_update_route(campaign_id):
    camp = get_campaign(campaign_id)
    if not camp:
        return jsonify({"error": "not found"}), 404
    role = get_user_role_in_org(get_jwt_identity(), camp["org_id"])
    if role not in ("admin", "owner"):
        return jsonify({"error": "admin or owner required"}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    if not title or not body:
        return jsonify({"error": "title and body required"}), 400
    upd = create_update(campaign_id, get_jwt_identity(), title, body)
    try:
        enqueue_campaign_update_notifications(campaign_id, upd["id"])
    except Exception:
        pass
    return jsonify(upd), 201


@campaigns.get("/<campaign_id>/updates/<update_id>")
def get_update_route(campaign_id, update_id):
    upd = get_update(update_id)
    if not upd or str(upd["campaign_id"]) != campaign_id:
        return jsonify({"error": "not found"}), 404
    return jsonify(upd), 200


@campaigns.patch("/<campaign_id>/updates/<update_id>")
@jwt_required()
def patch_update_route(campaign_id, update_id):
    upd = get_update(update_id)
    if not upd or str(upd["campaign_id"]) != campaign_id:
        return jsonify({"error": "not found"}), 404
    if str(upd["author_user_id"]) != get_jwt_identity():
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip() if "title" in data else None
    body = (data.get("body") or "").strip() if "body" in data else None
    updated = update_update(update_id, get_jwt_identity(), title, body)
    return jsonify(updated), 200


@campaigns.delete("/<campaign_id>/updates/<update_id>")
@jwt_required()
def delete_update_route(campaign_id, update_id):
    upd = get_update(update_id)
    if not upd or str(upd["campaign_id"]) != campaign_id:
        return jsonify({"error": "not found"}), 404
    if str(upd["author_user_id"]) != get_jwt_identity():
        return jsonify({"error": "forbidden"}), 403
    ok = delete_update(update_id, get_jwt_identity())
    return ("", 204) if ok else (jsonify({"error": "not found"}), 404)
