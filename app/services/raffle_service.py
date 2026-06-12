from __future__ import annotations
import hashlib
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
    get_org_member_emails,
    get_entry_by_donation,
    void_raffle_entry,
    get_valid_donation_count_for_entry,
)

_SIGNING_SECRET = os.getenv("JWT_SECRET", "dev-secret")
_SALT = "raffle-claim-v1"

# Platform-wide constant — change here to adjust claim window everywhere
RAFFLE_CLAIM_WINDOW_HOURS = 48


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_SIGNING_SECRET, salt=_SALT)


def generate_claim_token(raffle_id: str, entry_id: str) -> str:
    return _serializer().dumps({"raffle_id": raffle_id, "entry_id": entry_id})


def verify_claim_token(token: str) -> Tuple[str, str]:
    """Return (raffle_id, entry_id) or raise SignatureExpired / BadSignature."""
    data = _serializer().loads(token, max_age=RAFFLE_CLAIM_WINDOW_HOURS * 3600)
    return data["raffle_id"], data["entry_id"]


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _build_claim_url(token: str) -> str:
    base = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return f"{base}/raffles/claim?token={token}"


def _token_attempt_key(token: str) -> str:
    digest = hashlib.sha256(token.encode()).hexdigest()[:16]
    return f"raffle_claim_attempt:{digest}"


def execute_raffle_draw(raffle_id: str) -> None:
    """Draw a winner for the given raffle. Handles no-entries case (cancels raffle)."""
    from app.services.raffle_email_service import (
        send_raffle_winner_email,
        send_raffle_org_winner_drawn,
        send_raffle_org_no_entries,
    )
    from app.models.campaign import get_campaign

    raffle = get_raffle_by_id(raffle_id)
    if not raffle:
        return

    # Look up org for self-dealing exclusion check
    camp = get_campaign(raffle["campaign_id"])
    member_emails: set = get_org_member_emails(camp["org_id"]) if camp else set()

    entries = get_undrawn_entries(raffle_id)
    if not entries:
        update_raffle(raffle_id, status="cancelled", ended_at=_now_utc())
        try:
            send_raffle_org_no_entries(raffle)
        except Exception as e:
            print(f"[raffle] send_raffle_org_no_entries error: {e}", flush=True)
        return

    # Draw, skipping ineligible org members
    winner = secrets.choice(entries)
    remaining = list(entries)
    while winner["donor_email"].lower() in member_emails:
        create_draw_log(raffle_id, winner["id"], outcome="ineligible")
        remaining = [e for e in remaining if e["id"] != winner["id"]]
        if not remaining:
            winner = None
            break
        winner = secrets.choice(remaining)

    if winner is None:
        update_raffle(raffle_id, status="cancelled", ended_at=_now_utc())
        try:
            send_raffle_org_no_entries(raffle)
        except Exception as e:
            print(f"[raffle] send_raffle_org_no_entries error (all ineligible): {e}", flush=True)
        return

    claim_deadline = _now_utc() + timedelta(hours=RAFFLE_CLAIM_WINDOW_HOURS)

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


def validate_claim_token(token: str) -> Tuple[int, Dict[str, Any]]:
    """
    Step 1 of the two-step claim: validate token and return prize info.
    Does NOT claim the prize.
    """
    try:
        raffle_id, entry_id = verify_claim_token(token)
    except SignatureExpired:
        return 410, {"error": "This claim link has expired."}
    except (BadSignature, Exception):
        return 400, {"error": "Invalid claim link."}

    raffle = get_raffle_by_id(raffle_id)
    if not raffle:
        return 404, {"error": "Raffle not found."}

    if raffle.get("claim_token_used_at"):
        return 410, {"error": "This claim link has already been used."}

    if raffle["status"] == "claimed":
        return 410, {"error": "This claim link has already been used."}

    if raffle["status"] not in ("winner_pending",):
        return 410, {"error": "This raffle is no longer accepting claims."}

    entry = get_entry_by_id(entry_id)
    if not entry or entry["raffle_id"] != raffle_id:
        return 400, {"error": "Invalid claim link."}

    if raffle.get("winner_entry_id") != entry_id:
        return 410, {"error": "This claim link is no longer valid."}

    now = _now_utc()
    if raffle.get("claim_deadline") and raffle["claim_deadline"] < now:
        return 410, {"error": "This claim link has expired."}

    # Build a masked email hint for UX (e.g. "j***e@example.com")
    email = entry.get("donor_email", "")
    local, _, domain = email.partition("@")
    if len(local) > 1:
        hint = local[0] + "***" + local[-1] + "@" + domain
    else:
        hint = "***@" + domain

    return 200, {
        "valid": True,
        "prize_name": raffle.get("prize_name"),
        "donor_email_hint": hint,
    }


def claim_prize(token: str, email: str) -> Tuple[int, Dict[str, Any]]:
    """
    Step 2 of the two-step claim: verify email matches entry, then claim.
    Rate limiting for failed attempts is handled in the route layer.
    """
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

    if raffle.get("claim_token_used_at"):
        return 410, {"error": "This claim link has already been used."}

    if raffle["status"] == "claimed":
        return 410, {"error": "This claim link has already been used."}

    if raffle["status"] not in ("winner_pending",):
        return 410, {"error": "This raffle is no longer accepting claims."}

    entry = get_entry_by_id(entry_id)
    if not entry or entry["raffle_id"] != raffle_id:
        return 400, {"error": "Invalid claim link."}

    if raffle.get("winner_entry_id") != entry_id:
        return 410, {"error": "This claim link is no longer valid."}

    now = _now_utc()
    if raffle.get("claim_deadline") and raffle["claim_deadline"] < now:
        return 410, {"error": "This claim link has expired."}

    # Email confirmation check
    if entry["donor_email"].lower() != (email or "").strip().lower():
        return 400, {"error": "email_mismatch"}

    log = get_current_draw_log(raffle_id)
    if log and log["outcome"] == "notified":
        update_draw_log(log["id"], outcome="claimed", claimed_at=now)

    update_raffle(raffle_id, status="claimed", claim_token_used_at=now)

    try:
        send_raffle_org_winner_claimed(raffle, entry)
    except Exception as e:
        print(f"[raffle] send_raffle_org_winner_claimed error: {e}", flush=True)

    from app.models.campaign import get_campaign
    campaign = get_campaign(raffle.get("campaign_id", ""))
    org_name = (campaign or {}).get("title", "the organization")

    return 200, {
        "message": f"You've claimed your prize! {org_name} will be in touch to arrange delivery.",
        "claimed": True,
    }


def handle_donation_voided(donation_id: str, reason: str) -> None:
    """Called when a donation is refunded or chargebacked. Voids raffle entry if applicable."""
    from app.services.raffle_email_service import send_raffle_org_winner_voided

    entry = get_entry_by_donation(donation_id)
    if not entry:
        return

    raffle = get_raffle_by_id(entry["raffle_id"])
    if not raffle or raffle["status"] in ("cancelled", "unclaimed"):
        return

    # If donor has other valid donations to this campaign, keep them eligible
    valid_count = get_valid_donation_count_for_entry(raffle["id"], entry["donor_email"])
    if valid_count > 0:
        return

    void_raffle_entry(entry["id"], reason)

    # If this entry is the current winner, redraw
    if raffle.get("winner_entry_id") == entry["id"]:
        current_log = get_current_draw_log(raffle["id"])
        if current_log and current_log["outcome"] in ("notified", "claimed"):
            update_draw_log(current_log["id"], outcome="voided")

        was_claimed = raffle["status"] == "claimed"
        new_void_count = int(raffle.get("void_redraws") or 0) + 1
        update_raffle(
            raffle["id"],
            status="drawing",
            void_redraws=new_void_count,
            winner_entry_id=None,
            claim_deadline=None,
            claim_token_used_at=None,
        )

        try:
            execute_raffle_draw(raffle["id"])
        except Exception as e:
            print(f"[raffle] void redraw error: {e}", flush=True)

        if was_claimed:
            try:
                send_raffle_org_winner_voided(raffle, entry, reason)
            except Exception as e:
                print(f"[raffle] send_raffle_org_winner_voided error: {e}", flush=True)
