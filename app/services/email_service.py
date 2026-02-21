from __future__ import annotations
import os
from typing import Tuple, Dict, Any, Optional
from app.utils.db import get_db_connection
from app.models.donation import get_donation
from app.models.campaign import get_campaign
from app.models.email_receipt import render_receipt_content, render_winner_content
from app.models.org_email_settings import get_email_settings
from app.utils.email_sender import send_email

DEV_EMAIL_LOG_ONLY = os.getenv("DEV_EMAIL_LOG_ONLY", "1") == "1"


def _build_receipt(d: Dict[str, Any], camp: Dict[str, Any]) -> Tuple[str, str, str]:
    to_email = d.get("donor_email")
    amount = round(int(d["amount_cents"]) / 100.0, 2)
    subj = f"Thanks for your donation to {camp['title']}!"
    text = (
        f"Hi,\n\n"
        f"Thank you for your donation of ${amount:.2f} to {camp['title']}.\n"
        f"Campaign: {camp['title']} (#{camp['id']})\n"
        f"Currency: {d.get('currency','usd').upper()}\n\n"
        f"— The Team\n"
    )
    html = None
    return to_email, subj, text if not html else html


def ensure_receipt_for_donation(donation_id: str) -> None:
    """
    Idempotent: one row per donation_id. If already sent (sent_at not null),
    do nothing. Otherwise render org-branded content and store it (subject,
    body_text, body_html), and mark sent_at.
    """
    d = get_donation(donation_id)
    if not d or not d.get("donor_email"):
        return
    camp = get_campaign(d["campaign_id"])
    if not camp:
        return

    content = render_receipt_content(d["org_id"], d)
    subject = content["subject"]
    body_text = content["body_text"]
    body_html = content["body_html"]
    to_email = d["donor_email"]

    org_settings = get_email_settings(d["org_id"])
    from_email = (org_settings or {}).get("from_email")
    from_name = (org_settings or {}).get("from_name")
    reply_to = (org_settings or {}).get("reply_to")
    bcc_to = (org_settings or {}).get("bcc_to")

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, sent_at FROM email_receipts WHERE donation_id=%s",
            (donation_id,),
        )
        row = cur.fetchone()
        if row and row[1]:
            return

        receipt_id = row[0] if row else None
        if not receipt_id:
            cur.execute(
                """
                INSERT INTO email_receipts
                    (donation_id, to_email, subject, body_text, body_html)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (donation_id, to_email, subject, body_text, body_html),
            )
            receipt_id = cur.fetchone()[0]
        else:
            cur.execute(
                """
                UPDATE email_receipts
                   SET to_email = %s, subject = %s, body_text = %s, body_html = %s,
                       updated_at = now()
                 WHERE id = %s
                """,
                (to_email, subject, body_text, body_html, receipt_id),
            )
        conn.commit()

    if DEV_EMAIL_LOG_ONLY:
        print(f"[email][dev] to={to_email} subj={subject}")
        print(body_text)
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE email_receipts
                   SET sent_at = now(), provider = 'dev_log', updated_at = now()
                 WHERE id = %s
                """,
                (receipt_id,),
            )
            conn.commit()
        return

    result, msg_id_or_err = send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        from_email=from_email,
        from_name=from_name,
        reply_to=reply_to,
        bcc=bcc_to,
    )
    with get_db_connection() as conn, conn.cursor() as cur:
        if result and msg_id_or_err:
            cur.execute(
                """
                UPDATE email_receipts
                   SET sent_at = now(), provider = %s, provider_msg_id = %s,
                       last_error = NULL, updated_at = now()
                 WHERE id = %s
                """,
                (result, msg_id_or_err, receipt_id),
            )
        else:
            cur.execute(
                """
                UPDATE email_receipts
                   SET last_error = %s, updated_at = now()
                 WHERE id = %s
                """,
                (msg_id_or_err or "Unknown error", receipt_id),
            )
        conn.commit()


def send_winner_email(
    org_id: str,
    campaign_title: str,
    winner_email: str,
    prize_cents: int | None = None,
) -> Optional[str]:
    """
    Send winner notification email. Returns error message on failure, None on success.
    prize_cents: optional cash prize amount in cents (e.g. 100000 = $1000).
    """
    if not winner_email or not winner_email.strip():
        return None
    content = render_winner_content(
        org_id, campaign_title, winner_email, prize_cents=prize_cents
    )
    org_settings = get_email_settings(org_id)
    from_email = (org_settings or {}).get("from_email")
    from_name = (org_settings or {}).get("from_name")
    reply_to = (org_settings or {}).get("reply_to")
    bcc_to = (org_settings or {}).get("bcc_to")
    if DEV_EMAIL_LOG_ONLY:
        print(f"[email][dev] winner to={winner_email} subj={content['subject']}")
        return None
    result, msg_id_or_err = send_email(
        to_email=winner_email.strip(),
        subject=content["subject"],
        body_text=content["body_text"],
        body_html=content["body_html"],
        from_email=from_email,
        from_name=from_name,
        reply_to=reply_to,
        bcc=bcc_to,
    )
    return None if (result and msg_id_or_err) else (msg_id_or_err or "Unknown error")
