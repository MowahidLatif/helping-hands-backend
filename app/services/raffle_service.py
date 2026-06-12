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
    get_deletion_requested_entries,
    hard_delete_entries_by_ids,
    get_all_entries_for_raffle,
    delete_all_entries_for_raffle,
    anonymize_draw_log,
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


def execute_raffle_draw(raffle_id: str, triggered_by: str = "scheduler") -> None:
    """Draw a winner for the given raffle. Handles no-entries case (cancels raffle)."""
    from app.services.raffle_email_service import (
        send_raffle_winner_email,
        send_raffle_org_winner_drawn,
        send_raffle_org_no_entries,
        send_raffle_threshold_not_met,
    )
    from app.models.campaign import get_campaign
    from app.models.raffle import get_entry_count

    raffle = get_raffle_by_id(raffle_id)
    if not raffle:
        return

    # Scale-only: minimum entry threshold check
    min_entries = raffle.get("min_entries")
    if min_entries:
        actual_count = get_entry_count(raffle_id)
        if actual_count < min_entries:
            update_raffle(raffle_id, status="cancelled_threshold", ended_at=_now_utc())
            _cleanup_deletion_requested(raffle_id, raffle)
            try:
                send_raffle_threshold_not_met(raffle, actual_count)
            except Exception as e:
                print(f"[raffle] send_raffle_threshold_not_met error: {e}", flush=True)
            return

    # Look up org for self-dealing exclusion check
    camp = get_campaign(raffle["campaign_id"])
    member_emails: set = get_org_member_emails(camp["org_id"]) if camp else set()

    entries = get_undrawn_entries(raffle_id)
    if not entries:
        update_raffle(raffle_id, status="cancelled", ended_at=_now_utc())
        _cleanup_deletion_requested(raffle_id, raffle)
        try:
            send_raffle_org_no_entries(raffle)
        except Exception as e:
            print(f"[raffle] send_raffle_org_no_entries error: {e}", flush=True)
        return

    # Draw, skipping ineligible org members
    winner = secrets.choice(entries)
    remaining = list(entries)
    while winner["donor_email"].lower() in member_emails:
        create_draw_log(raffle_id, winner["id"], outcome="ineligible", triggered_by=triggered_by)
        remaining = [e for e in remaining if e["id"] != winner["id"]]
        if not remaining:
            winner = None
            break
        winner = secrets.choice(remaining)

    if winner is None:
        update_raffle(raffle_id, status="cancelled", ended_at=_now_utc())
        _cleanup_deletion_requested(raffle_id, raffle)
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
    create_draw_log(raffle_id, winner["id"], triggered_by=triggered_by)

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


def run_campaign_end_date_check() -> int:
    """Hourly job: complete campaigns whose ends_at has passed, then trigger payout + raffle draw."""
    from app.models.campaign import get_active_campaigns_past_end_date, force_complete_campaign
    from app.tasks import enqueue_campaign_payout

    count = 0
    for campaign_id in get_active_campaigns_past_end_date():
        did_complete = force_complete_campaign(campaign_id)
        if did_complete:
            try:
                enqueue_campaign_payout(campaign_id)
            except Exception as e:
                print(f"[end-date payout error] campaign={campaign_id}: {e}", flush=True)
            try:
                trigger_raffle_draw_if_active(campaign_id)
            except Exception as e:
                print(f"[end-date raffle draw error] campaign={campaign_id}: {e}", flush=True)
            count += 1
    return count


def _cleanup_deletion_requested(raffle_id: str, raffle: dict) -> None:
    """After a raffle reaches a terminal state, hard-delete any deletion-requested entries."""
    try:
        from app.services.raffle_email_service import send_deletion_confirmation_email
        entries = get_deletion_requested_entries(raffle_id)
        if entries:
            hard_delete_entries_by_ids([e["id"] for e in entries])
            for entry in entries:
                try:
                    send_deletion_confirmation_email(entry["donor_email"], raffle)
                except Exception as e:
                    print(f"[deletion confirm email] {entry.get('donor_email')}: {e}", flush=True)
    except Exception as e:
        print(f"[deletion cleanup] raffle={raffle_id}: {e}", flush=True)


def run_raffle_purge_job() -> int:
    """Nightly job: purge entrant data from raffles that ended more than 30 days ago."""
    from app.utils.db import get_db_connection
    from app.services.raffle_email_service import send_raffle_purge_notifications

    sql = """
        SELECT id, ended_at, prize_name, campaign_id
        FROM raffles
        WHERE status IN ('claimed', 'unclaimed', 'cancelled', 'cancelled_threshold')
          AND ended_at < NOW() - INTERVAL '30 days'
          AND EXISTS (
              SELECT 1 FROM raffle_entries WHERE raffle_id = raffles.id
          )
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        due = [dict(zip(cols, r)) for r in rows]

    count = 0
    for raffle in due:
        raffle_id = raffle["id"]
        try:
            entries = get_all_entries_for_raffle(raffle_id)
            purge_emails = [
                e["donor_email"]
                for e in entries
                if e.get("donor_email") and not e.get("deletion_requested")
            ]
            delete_all_entries_for_raffle(raffle_id)
            anonymize_draw_log(raffle_id)
            if purge_emails:
                try:
                    send_raffle_purge_notifications(raffle, purge_emails)
                except Exception as e:
                    print(f"[purge notifications] raffle={raffle_id}: {e}", flush=True)
            count += 1
        except Exception as e:
            print(f"[purge job] raffle={raffle_id}: {e}", flush=True)

    return count


def _emit_cloudwatch_metric(name: str, value: float = 1.0) -> None:
    try:
        import boto3
        boto3.client("cloudwatch").put_metric_data(
            Namespace="HHF/Raffle",
            MetricData=[{"MetricName": name, "Value": value, "Unit": "Count"}],
        )
    except Exception as e:
        print(f"[cloudwatch metric error] name={name}: {e}", flush=True)


def run_raffle_sweep_job() -> int:
    """
    Hourly sweep: find raffles that are still 'active' but their campaign
    completed more than 1 hour ago (scheduler miss recovery).
    """
    sql = """
        SELECT r.id
        FROM raffles r
        JOIN campaigns c ON c.id = r.campaign_id
        WHERE r.status = 'active'
          AND c.status = 'completed'
          AND c.updated_at < NOW() - INTERVAL '1 hour'
    """
    from app.utils.db import get_db_connection
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        stranded_ids = [row[0] for row in cur.fetchall()]

    caught = 0
    for raffle_id in stranded_ids:
        update_raffle(raffle_id, status="drawing")
        try:
            execute_raffle_draw(raffle_id, triggered_by="sweep")
            caught += 1
        except Exception as e:
            print(f"[raffle sweep] draw error for raffle {raffle_id}: {e}", flush=True)
            update_raffle(raffle_id, status="active")

    if caught > 0:
        _emit_cloudwatch_metric("RaffleSweepCaught", float(caught))

    return caught


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
    _cleanup_deletion_requested(raffle_id, raffle)

    try:
        send_raffle_org_winner_claimed(raffle, entry)
    except Exception as e:
        print(f"[raffle] send_raffle_org_winner_claimed error: {e}", flush=True)

    try:
        from app.tasks import enqueue_non_winner_emails
        enqueue_non_winner_emails(raffle_id)
    except Exception as e:
        print(f"[raffle] enqueue_non_winner_emails error: {e}", flush=True)

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
