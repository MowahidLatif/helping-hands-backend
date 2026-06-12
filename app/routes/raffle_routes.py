from __future__ import annotations
import hashlib
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
    get_raffle_entries,
)
from app.models.campaign import get_campaign
from app.models.org_user import get_user_role_in_org
from app.utils.tier_features import get_org_tier, TIER_LIMITS
from app.utils.rate_limit import is_rate_limited, rate_limit_key, rate_limit_exceeded_response
from app.services.raffle_service import (
    validate_claim_token,
    claim_prize,
    RAFFLE_CLAIM_WINDOW_HOURS,
)
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
        "prize_value_cents": raffle.get("prize_value_cents"),
        "min_entries": raffle.get("min_entries"),
        "status": raffle["status"],
        "redraw_count": raffle.get("redraw_count", 0),
        "max_redraws": raffle.get("max_redraws", 5),
        "void_redraws": raffle.get("void_redraws", 0),
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

    prize_value_cents = body.get("prize_value_cents")
    if prize_value_cents is None:
        return jsonify({"error": "prize_value_cents is required"}), 400
    try:
        prize_value_cents = int(prize_value_cents)
        if prize_value_cents <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "prize_value_cents must be a positive integer (in cents)"}), 400

    compliance_ack = body.get("compliance_ack", False)
    if not compliance_ack:
        return jsonify({"error": "compliance acknowledgment is required"}), 400

    min_entries = None
    if "min_entries" in body:
        locked_tier = camp.get("locked_tier") or 1
        if locked_tier < 3:
            return jsonify({"error": "min_entries is only available on the Scale plan", "tier_gate": "min_entries"}), 422
        try:
            min_entries = int(body["min_entries"])
            if min_entries < 2:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "min_entries must be an integer >= 2"}), 400

    raffle = create_raffle(
        campaign_id=campaign_id,
        prize_name=prize_name,
        prize_description=prize_description,
        prize_image_url=prize_image_url,
        compliance_ack_at=_now_utc(),
        prize_value_cents=prize_value_cents,
        min_entries=min_entries,
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

    if "prize_value_cents" in body:
        try:
            val = int(body["prize_value_cents"])
            if val <= 0:
                raise ValueError
            updates["prize_value_cents"] = val
        except (ValueError, TypeError):
            return jsonify({"error": "prize_value_cents must be a positive integer"}), 400

    if "min_entries" in body:
        locked_tier = camp.get("locked_tier") or 1
        if locked_tier < 3:
            return jsonify({"error": "min_entries is only available on the Scale plan", "tier_gate": "min_entries"}), 422
        raw_min = body["min_entries"]
        if raw_min is None:
            updates["min_entries"] = None
        else:
            try:
                val = int(raw_min)
                if val < 2:
                    raise ValueError
                updates["min_entries"] = val
            except (ValueError, TypeError):
                return jsonify({"error": "min_entries must be an integer >= 2 or null to remove"}), 400

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
            "triggered_by": row.get("triggered_by"),
            "notified_at": row["notified_at"].isoformat() if row.get("notified_at") else None,
            "claimed_at": row["claimed_at"].isoformat() if row.get("claimed_at") else None,
            "winner_email": claimed_winner_email,
        }

    response: dict = {
        "raffle": _serialize_raffle(raffle, include_winner_email=True),
        "entry_count": count,
        "draw_log": [_serialize_log(r) for r in draw_log],
    }

    # Scale (locked_tier >= 3): include full entrant list
    if (camp.get("locked_tier") or 1) >= 3:
        def _serialize_entry(e: dict) -> dict:
            return {
                "id": e["id"],
                "donor_email": e.get("donor_email"),
                "donor_first_name": e.get("donor_first_name"),
                "donor_last_name": e.get("donor_last_name"),
                "display_consent": e.get("display_consent"),
                "source": e.get("source"),
                "voided": e.get("voided", False),
                "void_reason": e.get("void_reason"),
                "deletion_requested": e.get("deletion_requested", False),
                "created_at": e["created_at"].isoformat() if e.get("created_at") else None,
            }
        entries = get_raffle_entries(raffle_id)
        response["entries"] = [_serialize_entry(e) for e in entries]
    else:
        response["entries"] = None
        response["entries_note"] = "Full entrant list is available on the Scale plan."

    return jsonify(response), 200


# ---------------------------------------------------------------------------
# Manual draw
# ---------------------------------------------------------------------------

@raffle_bp.post("/api/orgs/raffles/<raffle_id>/manual-draw")
@jwt_required()
def manual_draw(raffle_id: str):
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

    if raffle["status"] != "active":
        return jsonify({"error": "raffle must be in active status to draw manually"}), 422
    if camp.get("status") != "completed":
        return jsonify({"error": "campaign must be completed before drawing manually"}), 422
    if raffle.get("winner_entry_id"):
        return jsonify({"error": "a winner has already been drawn"}), 422

    from app.services.raffle_service import execute_raffle_draw
    update_raffle(raffle_id, status="drawing")
    try:
        execute_raffle_draw(raffle_id, triggered_by="org_manual")
    except Exception as e:
        update_raffle(raffle_id, status="active")
        return jsonify({"error": f"draw failed: {e}"}), 500

    return jsonify({"ok": True}), 200


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

    campaign_end_date = camp.get("ends_at") or None

    from app.models.org import get_organization
    org = get_organization(camp["org_id"])
    org_timezone = (org or {}).get("timezone", "UTC") or "UTC"

    payload = _serialize_raffle(raffle)
    payload["campaign_end_date"] = campaign_end_date.isoformat() if campaign_end_date else None
    payload["timezone"] = org_timezone
    payload["free_entry_url"] = f"/campaigns/{slug}/raffle/free-entry"
    payload["rules_url"] = f"/campaigns/{slug}/raffle/rules"
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
        "prize_value_cents": raffle.get("prize_value_cents"),
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

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM raffle_entries WHERE raffle_id = %s AND donor_email = %s",
            (raffle["id"], donor_email),
        )
        if cur.fetchone():
            return jsonify({"error": "this email is already entered in the raffle"}), 409

    entry = upsert_raffle_entry(
        raffle_id=raffle["id"],
        donor_email=donor_email,
        donor_first_name=donor_first_name,
        donor_last_name=donor_last_name,
        display_consent=False,
        source="free_entry",
        donation_id=None,
    )

    try:
        from app.services.raffle_email_service import send_raffle_free_entry_confirmation
        send_raffle_free_entry_confirmation(entry, raffle)
    except Exception as e:
        print(f"[raffle] free_entry_confirmation email error: {e}", flush=True)

    try:
        from app.realtime import socketio
        socketio.emit(
            "raffle_entry",
            {"campaign_id": str(camp["id"]), "raffle_id": str(raffle["id"])},
            to=f"campaign:{camp['id']}",
        )
    except Exception as e:
        print(f"[raffle] socketio emit raffle_entry (free) error: {e}", flush=True)

    return jsonify({"message": "You've been entered! Good luck."}), 201


# ---------------------------------------------------------------------------
# Claim routes (two-step)
# ---------------------------------------------------------------------------

@raffle_bp.get("/api/raffles/claim")
def validate_claim():
    """Step 1: validate token and return prize info. Does NOT claim."""
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "token is required"}), 400
    status_code, payload = validate_claim_token(token)
    return jsonify(payload), status_code


@raffle_bp.post("/api/raffles/claim")
def do_claim():
    """Step 2: confirm email and complete the claim."""
    body = request.get_json(force=True, silent=True) or {}
    token = (body.get("token") or "").strip()
    email = (body.get("email") or "").strip().lower()

    if not token:
        return jsonify({"error": "token is required"}), 400
    if not email:
        return jsonify({"error": "email is required"}), 400

    # Rate limit failed attempts per token to prevent guessing
    attempt_key = f"raffle_claim_attempt:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
    if is_rate_limited(attempt_key, limit=5, window_seconds=3600):
        return jsonify({"error": "Too many failed attempts. Please try again in 1 hour."}), 429

    status_code, payload = claim_prize(token, email)

    if status_code == 400 and payload.get("error") == "email_mismatch":
        # Consume an attempt on mismatch
        is_rate_limited(attempt_key, limit=5, window_seconds=3600)
        return jsonify({"error": "Email does not match. Please check and try again."}), 400

    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Deletion request (PIPEDA/GDPR)
# ---------------------------------------------------------------------------

@raffle_bp.post("/api/raffle-entries/deletion-request")
def request_entry_deletion():
    """
    No-auth endpoint: flag entries for deletion (hold if active raffle, delete immediately if terminal).
    Rate-limited to 3/hr per IP. Always returns 200 to avoid leaking whether email exists.
    """
    ip_key = f"raffle_deletion_request:{rate_limit_key()}"
    if is_rate_limited(ip_key, limit=3, window_seconds=3600):
        return rate_limit_exceeded_response(3)

    body = request.get_json(force=True, silent=True) or {}
    donor_email = (body.get("email") or "").strip().lower()
    if not donor_email or "@" not in donor_email:
        return jsonify({"ok": True}), 200

    from app.models.raffle import (
        mark_entry_deletion_requested,
        get_entries_in_terminal_raffles_by_email,
        hard_delete_entries_by_ids,
    )
    from app.services.raffle_email_service import send_deletion_confirmation_email

    # Immediately delete entries in terminal raffles
    terminal_entries = get_entries_in_terminal_raffles_by_email(donor_email)
    if terminal_entries:
        for entry in terminal_entries:
            try:
                raffle = get_raffle_by_id(entry["raffle_id"])
                if raffle:
                    send_deletion_confirmation_email(entry["donor_email"], raffle)
            except Exception:
                pass
        hard_delete_entries_by_ids([e["id"] for e in terminal_entries])

    # Flag entries in active raffles for deletion at raffle conclusion
    mark_entry_deletion_requested(donor_email)

    return jsonify({"ok": True}), 200


# ---------------------------------------------------------------------------
# Official rules page (public)
# ---------------------------------------------------------------------------

@raffle_bp.get("/api/campaigns/<slug>/raffle/rules")
def get_raffle_rules(slug: str):
    camp = _get_campaign_by_slug_or_id(slug)
    if not camp:
        return jsonify({"error": "campaign not found"}), 404
    raffle = get_raffle_by_campaign(camp["id"])
    if not raffle:
        return jsonify({"error": "no raffle for this campaign"}), 404

    from app.models.org import get_organization
    org = get_organization(camp["org_id"])

    entry_start = camp.get("created_at")
    entry_end = camp.get("ends_at")

    return jsonify({
        "org_name": (org or {}).get("name", "the organization"),
        "campaign_title": camp.get("title"),
        "entry_period_start": entry_start.isoformat() if entry_start else None,
        "entry_period_end": entry_end.isoformat() if entry_end else None,
        "prize_name": raffle["prize_name"],
        "prize_description": raffle.get("prize_description"),
        "prize_value_cents": raffle.get("prize_value_cents"),
        "free_entry_url": f"/campaigns/{slug}/raffle/free-entry",
        "claim_window_hours": RAFFLE_CLAIM_WINDOW_HOURS,
    }), 200
