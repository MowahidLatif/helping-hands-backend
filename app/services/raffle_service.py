from __future__ import annotations
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Tuple, Dict, Any

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from app.models.raffle import (
    get_raffle_by_campaign,
    get_raffle_by_id,
    update_raffle,
    get_undrawn_entries,
    create_draw_log,
    update_draw_log,
    get_current_draw_log,
    get_pending_claim_raffles,
    get_entry_by_id,
)

_SIGNING_SECRET = os.getenv("JWT_SECRET", "dev-secret")
_SALT = "raffle-claim-v1"
_CLAIM_HOURS = 24


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_SIGNING_SECRET, salt=_SALT)


def generate_claim_token(raffle_id: str, entry_id: str) -> str:
    return _serializer().dumps({"raffle_id": raffle_id, "entry_id": entry_id})


def verify_claim_token(token: str) -> Tuple[str, str]:
    """Return (raffle_id, entry_id) or raise SignatureExpired / BadSignature."""
    data = _serializer().loads(token, max_age=_CLAIM_HOURS * 3600)
    return data["raffle_id"], data["entry_id"]


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def execute_raffle_draw(raffle_id: str) -> None:
    """Draw a winner for the given raffle. Handles no-entries case (cancels raffle)."""
    from app.services.raffle_email_service import (
        send_raffle_winner_email,
        send_raffle_org_winner_drawn,
        send_raffle_org_no_entries,
    )

    raffle = get_raffle_by_id(raffle_id)
    if not raffle:
        return

    entries = get_undrawn_entries(raffle_id)
    if not entries:
        update_raffle(raffle_id, status="cancelled", ended_at=_now_utc())
        try:
            send_raffle_org_no_entries(raffle)
        except Exception as e:
            print(f"[raffle] send_raffle_org_no_entries error: {e}", flush=True)
        return

    winner = secrets.choice(entries)
    claim_deadline = _now_utc() + timedelta(hours=_CLAIM_HOURS)

    update_raffle(
        raffle_id,
        winner_entry_id=winner["id"],
        status="winner_pending",
        claim_deadline=claim_deadline,
        ended_at=_now_utc(),
    )
    create_draw_log(raffle_id, winner["id"])

    claim_token = generate_claim_token(raffle_id, winner["id"])
    claim_url = _build_claim_url(claim_token)

    try:
        send_raffle_winner_email(winner, raffle, claim_url)
    except Exception as e:
        print(f"[raffle] send_raffle_winner_email error: {e}", flush=True)

    try:
        send_raffle_org_winner_drawn(raffle, winner)
    except Exception as e:
        print(f"[raffle] send_raffle_org_winner_drawn error: {e}", flush=True)


def _build_claim_url(token: str) -> str:
    base = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return f"{base}/raffles/claim?token={token}"


def trigger_raffle_draw_if_active(campaign_id: str) -> None:
    """Called when a campaign completes — draws raffle if one is active."""
    raffle = get_raffle_by_campaign(campaign_id)
    if not raffle or raffle["status"] != "active":
        return
    update_raffle(raffle["id"], status="drawing")
    try:
        execute_raffle_draw(raffle["id"])
    except Exception as e:
        print(f"[raffle] execute_raffle_draw error for campaign {campaign_id}: {e}", flush=True)
        update_raffle(raffle["id"], status="active")


def process_expired_claims() -> int:
    """Nightly job: expire pending claims and trigger redraws. Returns count processed."""
    from app.services.raffle_email_service import (
        send_raffle_org_unclaimed,
    )

    raffles = get_pending_claim_raffles()
    count = 0
    for raffle in raffles:
        raffle_id = raffle["id"]
        log = get_current_draw_log(raffle_id)
        if log and log["outcome"] == "notified":
            update_draw_log(log["id"], outcome="expired")

        new_redraw_count = int(raffle.get("redraw_count") or 0) + 1
        max_redraws = int(raffle.get("max_redraws") or 5)
        remaining = get_undrawn_entries(raffle_id)

        if new_redraw_count >= max_redraws or not remaining:
            update_raffle(raffle_id, status="unclaimed", redraw_count=new_redraw_count)
            try:
                send_raffle_org_unclaimed(raffle, new_redraw_count)
            except Exception as e:
                print(f"[raffle] send_raffle_org_unclaimed error: {e}", flush=True)
        else:
            update_raffle(raffle_id, redraw_count=new_redraw_count)
            try:
                execute_raffle_draw(raffle_id)
            except Exception as e:
                print(f"[raffle] redraw error for {raffle_id}: {e}", flush=True)
        count += 1
    return count


def claim_prize(token: str) -> Tuple[int, Dict[str, Any]]:
    """Process a prize claim. Returns (status_code, payload)."""
    from app.services.raffle_email_service import send_raffle_org_winner_claimed

    try:
        raffle_id, entry_id = verify_claim_token(token)
    except SignatureExpired:
        return 410, {"error": "This claim link has expired."}
    except (BadSignature, Exception):
        return 400, {"error": "Invalid claim link."}

    raffle = get_raffle_by_id(raffle_id)
    if not raffle:
        return 404, {"error": "Raffle not found."}
    if raffle["status"] == "claimed":
        return 200, {"message": "Prize already claimed."}
    if raffle["status"] not in ("winner_pending",):
        return 410, {"error": "This raffle is no longer accepting claims."}

    entry = get_entry_by_id(entry_id)
    if not entry or entry["raffle_id"] != raffle_id:
        return 400, {"error": "Invalid claim link."}

    # Verify this entry is still the current winner
    if raffle.get("winner_entry_id") != entry_id:
        return 410, {"error": "This claim link is no longer valid."}

    now = _now_utc()
    if raffle.get("claim_deadline") and raffle["claim_deadline"] < now:
        return 410, {"error": "This claim link has expired."}

    log = get_current_draw_log(raffle_id)
    if log and log["outcome"] == "notified":
        update_draw_log(log["id"], outcome="claimed", claimed_at=now)

    update_raffle(raffle_id, status="claimed")

    try:
        send_raffle_org_winner_claimed(raffle, entry)
    except Exception as e:
        print(f"[raffle] send_raffle_org_winner_claimed error: {e}", flush=True)

    from app.models.campaign import get_campaign_by_id
    campaign = get_campaign_by_id(raffle.get("campaign_id", ""))
    org_name = (campaign or {}).get("title", "the organization")

    return 200, {
        "message": f"You've claimed your prize! {org_name} will be in touch to arrange delivery.",
        "claimed": True,
    }
