"""
Background tasks for RQ (Redis Queue).

Run worker: poetry run rq worker -u $REDIS_URL --with-scheduler
"""

from __future__ import annotations
import logging
import os

from app.services.email_service import ensure_receipt_for_donation
from app.services.ai_site_service import run_generation_job
from app.services.settlement_service import execute_campaign_payout
from app.utils.cache import REDIS_URL

logger = logging.getLogger(__name__)


def enqueue_receipt_email(donation_id: str) -> bool:
    """
    Enqueue ensure_receipt_for_donation for background processing.
    Returns True if enqueued, False if run synchronously (no queue).
    """
    use_queue = os.getenv("USE_EMAIL_QUEUE", "0") == "1"
    if not use_queue:
        ensure_receipt_for_donation(donation_id)
        return False

    try:
        from redis import Redis
        from rq import Queue

        conn = Redis.from_url(REDIS_URL, decode_responses=False)
        q = Queue("default", connection=conn)
        q.enqueue(ensure_receipt_for_donation, donation_id, job_timeout="2m")
        return True
    except Exception as e:
        # Fallback to sync if queue unavailable
        import warnings

        warnings.warn(f"RQ enqueue failed ({e}), running sync", stacklevel=0)
        ensure_receipt_for_donation(donation_id)
        return False


def enqueue_campaign_update_notifications(campaign_id: str, update_id: str) -> bool:
    """Enqueue notifications to campaign followers (donors) about a new update."""
    use_queue = os.getenv("USE_EMAIL_QUEUE", "0") == "1"
    if not use_queue:
        send_campaign_update_notifications(campaign_id, update_id)
        return False
    try:
        from redis import Redis
        from rq import Queue

        conn = Redis.from_url(REDIS_URL, decode_responses=False)
        q = Queue("default", connection=conn)
        q.enqueue(
            send_campaign_update_notifications, campaign_id, update_id, job_timeout="5m"
        )
        return True
    except Exception:
        send_campaign_update_notifications(campaign_id, update_id)
        return False


def enqueue_ai_site_generation(
    job_id: str,
    campaign_id: str,
    prompt: str,
    theme: dict | None = None,
) -> bool:
    """
    Enqueue AI generation job with retries.
    Returns True if enqueued, False if queue unavailable and run synchronously.
    """
    use_queue = os.getenv("USE_AI_GENERATION_QUEUE", "1") == "1"
    if not use_queue:
        run_generation_job(job_id, campaign_id, prompt, theme=theme)
        return False
    try:
        from redis import Redis
        from rq import Queue, Retry

        conn = Redis.from_url(REDIS_URL, decode_responses=False)
        q = Queue("ai_generation", connection=conn)
        q.enqueue(
            run_generation_job,
            job_id,
            campaign_id,
            prompt,
            theme,
            job_timeout="10m",
            retry=Retry(max=2, interval=[15, 45]),
            failure_ttl=86400,
        )
        return True
    except Exception:
        run_generation_job(job_id, campaign_id, prompt, theme=theme)
        return False


def enqueue_campaign_payout(campaign_id: str) -> bool:
    """
    Enqueue payout execution for a completed campaign.
    Returns True if queued, False if executed synchronously.
    """
    use_queue = os.getenv("USE_PAYOUT_QUEUE", "1") == "1"
    if not use_queue:
        execute_campaign_payout(campaign_id)
        return False
    try:
        from redis import Redis
        from rq import Queue, Retry

        conn = Redis.from_url(REDIS_URL, decode_responses=False)
        q = Queue("payouts", connection=conn)
        q.enqueue(
            execute_campaign_payout,
            campaign_id,
            job_timeout="5m",
            retry=Retry(max=2, interval=[20, 60]),
            failure_ttl=86400,
        )
        return True
    except Exception:
        execute_campaign_payout(campaign_id)
        return False


def send_campaign_update_notifications(campaign_id: str, update_id: str) -> None:
    """Notify campaign donors about a new update."""
    from app.models.campaign import get_campaign
    from app.models.campaign_update import get_update
    from app.models.donation import list_succeeded_for_campaign
    from app.utils.email_sender import send_email
    from app.models.org_email_settings import get_email_settings

    camp = get_campaign(campaign_id)
    upd = get_update(update_id)
    if not camp or not upd:
        return
    donors = list_succeeded_for_campaign(
        campaign_id, mode="per_donor", min_amount_cents=0
    )
    emails = {d["donor_email"] for d in donors if d.get("donor_email")}
    org_settings = get_email_settings(camp["org_id"]) or {}
    from_email = org_settings.get("from_email")
    from_name = org_settings.get("from_name")
    subject = f"New update: {upd['title']} – {camp['title']}"
    body_text = f"{upd['title']}\n\n{upd['body']}\n\n— {camp['title']}"
    body_html = f"<h2>{upd['title']}</h2><p>{upd['body']}</p><p>— {camp['title']}</p>"
    for to_addr in emails:
        try:
            send_email(
                to_email=to_addr,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_email=from_email,
                from_name=from_name,
            )
        except Exception as e:
            logger.error("send campaign update email to %s: %s", to_addr, e)


def run_billing_trial_reminders() -> int:
    """RQ/cron: send Day-6 trial-ending-tomorrow emails."""
    from app.services.billing_service import process_trial_day6_reminders
    return process_trial_day6_reminders()


def run_billing_grace_expiry() -> int:
    """RQ/cron: restrict accounts after payment grace period."""
    from app.services.billing_service import process_payment_grace_expiry
    return process_payment_grace_expiry()


def run_raffle_redraw_check() -> int:
    """RQ/cron (hourly): expire pending raffle claims and trigger redraws."""
    from app.services.raffle_service import process_expired_claims
    result = process_expired_claims()
    _enqueue_hourly(run_raffle_redraw_check)
    return result


def run_campaign_end_date_check() -> int:
    """RQ/cron (hourly): complete campaigns whose ends_at has passed, queue payout, trigger raffle draw."""
    from app.services.raffle_service import run_campaign_end_date_check as _check
    result = _check()
    _enqueue_hourly(run_campaign_end_date_check)
    return result


def run_raffle_sweep_job() -> int:
    """RQ/cron (hourly): catch stranded active raffles whose campaigns already completed."""
    from app.services.raffle_service import run_raffle_sweep_job as _sweep
    result = _sweep()
    _enqueue_hourly(run_raffle_sweep_job)
    return result


def run_raffle_purge_job() -> int:
    """RQ/cron (nightly): delete entrant data from raffles ended 30+ days ago."""
    from app.services.raffle_service import run_raffle_purge_job as _purge
    return _purge()


def enqueue_non_winner_emails(raffle_id: str) -> bool:
    """Enqueue non-winner thank-you emails after a raffle is claimed."""
    use_queue = os.getenv("USE_EMAIL_QUEUE", "0") == "1"
    if not use_queue:
        task_send_non_winner_emails(raffle_id)
        return False
    try:
        from redis import Redis
        from rq import Queue
        conn = Redis.from_url(REDIS_URL, decode_responses=False)
        q = Queue("default", connection=conn)
        q.enqueue(task_send_non_winner_emails, raffle_id, job_timeout="10m")
        return True
    except Exception:
        task_send_non_winner_emails(raffle_id)
        return False


def task_send_non_winner_emails(raffle_id: str) -> None:
    """Send non-winner thank-you emails for all non-winning, non-voided entrants."""
    from app.models.raffle import get_raffle_by_id, get_all_entries_for_raffle
    from app.services.raffle_email_service import send_raffle_non_winner_email

    raffle = get_raffle_by_id(raffle_id)
    if not raffle:
        return
    entries = get_all_entries_for_raffle(raffle_id)
    winner_id = raffle.get("winner_entry_id")
    non_winners = [
        e for e in entries
        if e["id"] != winner_id and not e.get("voided") and not e.get("deletion_requested")
    ]
    for entry in non_winners:
        try:
            send_raffle_non_winner_email(entry, raffle)
        except Exception as e:
            logger.error("send non-winner email to %s: %s", entry.get("donor_email"), e)


def _enqueue_hourly(fn) -> None:
    """Re-enqueue fn to run again in 1 hour via RQ built-in scheduler."""
    from datetime import timedelta
    try:
        from redis import Redis
        from rq import Queue
        conn = Redis.from_url(REDIS_URL, decode_responses=False)
        Queue("default", connection=conn).enqueue_in(timedelta(hours=1), fn)
    except Exception as e:
        logger.warning("Could not reschedule %s: %s", getattr(fn, "__name__", fn), e)


def register_scheduled_jobs() -> None:
    """
    Seed the RQ scheduler with the first run of all recurring hourly jobs.
    Call once after deploying: poetry run python -c 'from app.tasks import register_scheduled_jobs; register_scheduled_jobs()'
    Each job self-reschedules via _enqueue_hourly() after it runs.
    """
    from datetime import timedelta
    try:
        from redis import Redis
        from rq import Queue
        conn = Redis.from_url(REDIS_URL, decode_responses=False)
        q = Queue("default", connection=conn)
        for fn in (run_raffle_redraw_check, run_campaign_end_date_check, run_raffle_sweep_job):
            q.enqueue_in(timedelta(minutes=5), fn)
        logger.info("Hourly background jobs seeded into RQ scheduler.")
    except Exception as e:
        logger.error("Failed to seed scheduled jobs: %s", e)
