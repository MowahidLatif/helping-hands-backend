"""
Background tasks for RQ (Redis Queue).

Run worker: poetry run rq worker -u $REDIS_URL --with-scheduler
"""

from __future__ import annotations
import os

from app.services.email_service import ensure_receipt_for_donation
from app.utils.cache import REDIS_URL


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
        except Exception:
            pass
