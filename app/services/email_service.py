from __future__ import annotations
import os
from typing import Tuple, Dict, Any
from app.utils.db import get_db_connection
from app.models.donation import get_donation
from app.models.campaign import get_campaign
from app.models.email_receipt import render_receipt_content

DEV_EMAIL_LOG_ONLY = os.getenv("DEV_EMAIL_LOG_ONLY", "1") == "1"
FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@example.com")


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

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, sent_at FROM email_receipts WHERE donation_id=%s",
            (donation_id,),
        )
        row = cur.fetchone()
        if row and row[1]:
            return

        if row:
            cur.execute(
                """
                UPDATE email_receipts
                   SET to_email = %s,
                       subject  = %s,
                       body_text= %s,
                       body_html= %s,
                       sent_at  = now(),
                       updated_at = now()
                 WHERE id = %s
                """,
                (to_email, subject, body_text, body_html, row[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO email_receipts
                    (donation_id, to_email, subject, body_text, body_html, sent_at)
                VALUES (%s, %s, %s, %s, %s, now())
                """,
                (donation_id, to_email, subject, body_text, body_html),
            )
        conn.commit()

    if DEV_EMAIL_LOG_ONLY:
        print(f"[email][dev] to={to_email} subj={subject}")
        print(body_text)
