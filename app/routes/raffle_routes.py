from __future__ import annotations
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from datetime import datetime, timezone

from app.models.raffle import (
    create_raffle,
    get_raffle_by_campaign,
    get_raffle_by_id,
    update_raffle,
    upsert_raffle_entry,
    get_entry_count,
    get_draw_log_for_raffle,
)
from app.models.campaign import get_campaign
from app.models.org_user import get_user_role_in_org
from app.utils.tier_features import get_org_tier, TIER_LIMITS
from app.utils.rate_limit import is_rate_limited, rate_limit_key, rate_limit_exceeded_response
from app.services.raffle_service import claim_prize
from app.utils.db import get_db_connection

raffle_bp = Blueprint("raffles", __name__)


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _serialize_raffle(raffle: dict, include_winner_email: bool = False) -> dict:
    entry = None
    if raffle.get("winner_entry_id"):
        from app.models.raffle import get_entry_by_id
        entry = get_entry_by_id(raffle["winner_entry_id"])

    winner_display_name = None
    winner_email_out = None
    if entry:
        if entry.get("display_consent") and raffle.get("status") == "claimed":
            first = entry.get("donor_first_name") or ""
            last = entry.get("donor_last_name") or ""
            last_initial = last[0] + "." if last else ""
            winner_display_name = f"{first} {last_initial}".strip() or None
        if include_winner_email and raffle.get("status") == "claimed":
            winner_email_out = entry.get("donor_email")

    out = {
        "id": raffle["id"],
        "campaign_id": raffle["campaign_id"],
        "prize_name": raffle["prize_name"],
        "prize_description": raffle.get("prize_description"),
        "prize_image_url": raffle.get("prize_image_url"),
        "status": raffle["status"],
        "redraw_count": raffle.get("redraw_count", 0),
        "max_redraws": raffle.get("max_redraws", 5),
        "claim_deadline": raffle["claim_deadline"].isoformat() if raffle.get("claim_deadline") else None,
        "created_at": raffle["created_at"].isoformat() if raffle.get("created_at") else None,
        "ended_at": raffle["ended_at"].isoformat() if raffle.get("ended_at") else None,
        "winner_display_name": winner_display_name,
    }
    if winner_email_out:
        out["winner_contact_email"] = winner_email_out
    return out


def _get_campaign_id_for_org(campaign_id: str, org_id: str) -> dict | None:
    camp = get_campaign(campaign_id)
    if not camp or camp.get("org_id") != org_id:
        return None
    return camp


# ---------------------------------------------------------------------------
# Org-authenticated routes
# ---------------------------------------------------------------------------

@raffle_bp.post("/api/campaigns/<campaign_id>/raffle")
@jwt_required()
def create_campaign_raffle(campaign_id: str):
    claims = get_jwt()
    user_id = get_jwt_identity()
    org_id = request.args.get("org_id") or claims.get("org_id")

    camp = _get_campaign_id_for_org(campaign_id, org_id)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404

    role = get_user_role_in_org(user_id, org_id)
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403

    tier = get_org_tier(org_id)
    if not TIER_LIMITS.get(tier, {}).get("raffle"):
        return jsonify({
            "error": "Raffles are available on Grow and Scale plans. Upgrade in Settings.",
            "tier_gate": "raffle",
        }), 403

    if get_raffle_by_campaign(campaign_id):
        return jsonify({"error": "a raffle already exists for this campaign"}), 409

    body = request.get_json(force=True, silent=True) or {}
    prize_name = (body.get("prize_name") or "").strip()
    if not prize_name:
        return jsonify({"error": "prize_name is required"}), 400
    if len(prize_name) > 120:
        return jsonify({"error": "prize_name must be 120 characters or fewer"}), 400

    prize_description = (body.get("prize_description") or "").strip() or None
    if prize_description and len(prize_description) > 1000:
        return jsonify({"error": "prize_description must be 1000 characters or fewer"}), 400

    prize_image_url = (body.get("prize_image_url") or "").strip() or None
    compliance_ack = body.get("compliance_ack", False)
    if not compliance_ack:
        return jsonify({"error": "compliance acknowledgment is required"}), 400

    raffle = create_raffle(
        campaign_id=campaign_id,
        prize_name=prize_name,
        prize_description=prize_description,
        prize_image_url=prize_image_url,
        compliance_ack_at=_now_utc(),
    )
    return jsonify(_serialize_raffle(raffle)), 201


@raffle_bp.patch("/api/campaigns/<campaign_id>/raffle")
@jwt_required()
def update_campaign_raffle(campaign_id: str):
    claims = get_jwt()
    user_id = get_jwt_identity()
    org_id = request.args.get("org_id") or claims.get("org_id")

    camp = _get_campaign_id_for_org(campaign_id, org_id)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404

    role = get_user_role_in_org(user_id, org_id)
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403

    raffle = get_raffle_by_campaign(campaign_id)
    if not raffle:
        return jsonify({"error": "no raffle for this campaign"}), 404

    if raffle["status"] not in ("active",):
        return jsonify({"error": "raffle prize details can only be edited while the raffle is active"}), 409

    body = request.get_json(force=True, silent=True) or {}
    updates: dict = {}

    if "prize_name" in body:
        prize_name = (body["prize_name"] or "").strip()
        if not prize_name or len(prize_name) > 120:
            return jsonify({"error": "prize_name must be 1–120 characters"}), 400
        updates["prize_name"] = prize_name

    if "prize_description" in body:
        desc = (body["prize_description"] or "").strip() or None
        if desc and len(desc) > 1000:
            return jsonify({"error": "prize_description must be 1000 characters or fewer"}), 400
        updates["prize_description"] = desc

    if "prize_image_url" in body:
        updates["prize_image_url"] = (body["prize_image_url"] or "").strip() or None

    if not updates:
        return jsonify(_serialize_raffle(raffle)), 200

    updated = update_raffle(raffle["id"], **updates)
    return jsonify(_serialize_raffle(updated)), 200


@raffle_bp.get("/api/orgs/raffles/<raffle_id>/entries")
@jwt_required()
def get_raffle_entries_for_org(raffle_id: str):
    claims = get_jwt()
    user_id = get_jwt_identity()
    org_id = request.args.get("org_id") or claims.get("org_id")

    raffle = get_raffle_by_id(raffle_id)
    if not raffle:
        return jsonify({"error": "not found"}), 404

    camp = get_campaign(raffle["campaign_id"])
    if not camp or camp.get("org_id") != org_id:
        return jsonify({"error": "not found"}), 404

    role = get_user_role_in_org(user_id, org_id)
    if role not in ("owner", "admin"):
        return jsonify({"error": "forbidden"}), 403

    count = get_entry_count(raffle_id)
    draw_log = get_draw_log_for_raffle(raffle_id)

    def _serialize_log(row: dict) -> dict:
        claimed_winner_email = None
        if row.get("outcome") == "claimed":
            from app.models.raffle import get_entry_by_id
            e = get_entry_by_id(row["entry_id"])
            claimed_winner_email = e.get("donor_email") if e else None
        return {
            "id": row["id"],
            "drawn_at": row["drawn_at"].isoformat() if row.get("drawn_at") else None,
            "outcome": row["outcome"],
            "notified_at": row["notified_at"].isoformat() if row.get("notified_at") else None,
            "claimed_at": row["claimed_at"].isoformat() if row.get("claimed_at") else None,
            "winner_email": claimed_winner_email,
        }

    return jsonify({
        "raffle": _serialize_raffle(raffle, include_winner_email=True),
        "entry_count": count,
        "draw_log": [_serialize_log(r) for r in draw_log],
    }), 200


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

def _get_campaign_by_slug_or_id(slug_or_id: str) -> dict | None:
    """Look up campaign by ID first, then by slug across orgs."""
    camp = get_campaign(slug_or_id)
    if camp:
        return camp
    sql = "SELECT id FROM campaigns WHERE slug = %s LIMIT 1"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (slug_or_id,))
        row = cur.fetchone()
        if row:
            return get_campaign(row[0])
    return None


@raffle_bp.get("/api/campaigns/<slug>/raffle/public")
def get_public_raffle(slug: str):
    camp = _get_campaign_by_slug_or_id(slug)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404

    raffle = get_raffle_by_campaign(camp["id"])
    if not raffle:
        return jsonify({"raffle": None}), 200

    campaign_end_date = camp.get("updated_at") or camp.get("created_at")

    payload = _serialize_raffle(raffle)
    payload["campaign_end_date"] = campaign_end_date.isoformat() if campaign_end_date else None
    payload["free_entry_url"] = f"/campaigns/{slug}/raffle/free-entry"
    payload["entry_count"] = get_entry_count(raffle["id"])
    return jsonify({"raffle": payload}), 200


@raffle_bp.get("/api/campaigns/<slug>/raffle/free-entry")
def free_entry_info(slug: str):
    camp = _get_campaign_by_slug_or_id(slug)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404
    raffle = get_raffle_by_campaign(camp["id"])
    if not raffle or raffle["status"] != "active":
        return jsonify({"error": "no active raffle for this campaign"}), 404
    return jsonify({
        "prize_name": raffle["prize_name"],
        "prize_description": raffle.get("prize_description"),
        "prize_image_url": raffle.get("prize_image_url"),
        "campaign_title": camp.get("title"),
    }), 200


@raffle_bp.post("/api/campaigns/<slug>/raffle/free-entry")
def submit_free_entry(slug: str):
    ip_key = f"raffle_free_entry:{rate_limit_key()}"
    if is_rate_limited(ip_key, limit=5, window_seconds=3600):
        return rate_limit_exceeded_response(5)

    camp = _get_campaign_by_slug_or_id(slug)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404

    raffle = get_raffle_by_campaign(camp["id"])
    if not raffle or raffle["status"] != "active":
        return jsonify({"error": "no active raffle for this campaign"}), 404

    body = request.get_json(force=True, silent=True) or {}
    donor_email = (body.get("email") or "").strip().lower()
    donor_first_name = (body.get("first_name") or "").strip() or None
    donor_last_name = (body.get("last_name") or "").strip() or None

    if not donor_email or "@" not in donor_email:
        return jsonify({"error": "a valid email is required"}), 400
    if not donor_first_name or not donor_last_name:
        return jsonify({"error": "first_name and last_name are required"}), 400

    from app.utils.db import get_db_connection as _db
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM raffle_entries WHERE raffle_id = %s AND donor_email = %s",
            (raffle["id"], donor_email),
        )
        if cur.fetchone():
            return jsonify({"error": "this email is already entered in the raffle"}), 409

    upsert_raffle_entry(
        raffle_id=raffle["id"],
        donor_email=donor_email,
        donor_first_name=donor_first_name,
        donor_last_name=donor_last_name,
        display_consent=False,
        source="free_entry",
        donation_id=None,
    )
    return jsonify({"message": "You've been entered! Good luck."}), 201


@raffle_bp.get("/api/raffles/claim")
def claim_raffle_prize():
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "token is required"}), 400
    status_code, payload = claim_prize(token)
    return jsonify(payload), status_code
