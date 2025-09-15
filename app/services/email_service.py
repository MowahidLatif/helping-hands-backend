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
    html = None  # keep simple for now
    return to_email, subj, text if not html else html


# def ensure_receipt_for_donation(donation_id: str) -> None:
#     """Idempotent: writes one row per donation_id and sends (or logs) once."""
#     d = get_donation(donation_id)
#     if not d or not d.get("donor_email"):
#         return
#     camp = get_campaign(d["campaign_id"])
#     if not camp:
#         return

#     to_email, subject, body_text = _build_receipt(d, camp)

#     with get_db_connection() as conn, conn.cursor() as cur:
#         # check if exists (idempotent)
#         cur.execute(
#             "SELECT id, sent_at FROM email_receipts WHERE donation_id=%s",
#             (donation_id,),
#         )
#         row = cur.fetchone()
#         if row and row[1]:
#             return  # already sent

#         # upsert skeleton
#         cur.execute(
#             """
#             INSERT INTO email_receipts (donation_id, to_email, subject, body_text, provider)
#             VALUES (%s, %s, %s, %s, %s)
#             ON CONFLICT (donation_id) DO UPDATE SET
#               to_email=EXCLUDED.to_email,
#               subject=EXCLUDED.subject,
#               body_text=EXCLUDED.body_text,
#               provider=EXCLUDED.provider
#             RETURNING id
#         """,
#             (
#                 donation_id,
#                 to_email,
#                 subject,
#                 body_text,
#                 "dev" if DEV_EMAIL_LOG_ONLY else "smtp",
#             ),
#         )
#         rec_id = cur.fetchone()[0]

#         if DEV_EMAIL_LOG_ONLY:
#             # mark as "sent" but only logged to console
#             print(f"[email][dev] to={to_email} subj={subject}\n{body_text}")
#             cur.execute(
#                 "UPDATE email_receipts SET sent_at=now() WHERE id=%s", (rec_id,)
#             )
#             conn.commit()
#             return

#         # Simple SMTP example (optional)
#         # import smtplib
#         # with smtplib.SMTP(os.getenv("SMTP_HOST","127.0.0.1"), int(os.getenv("SMTP_PORT","1025"))) as s:
#         #     msg = f"From: {FROM_EMAIL}\r\nTo: {to_email}\r\nSubject: {subject}\r\n\r\n{body_text}"
#         #     s.sendmail(FROM_EMAIL, [to_email], msg)
#         # cur.execute("UPDATE email_receipts SET sent_at=now(), provider_msg_id=%s WHERE id=%s", ("smtp:dev", rec_id))
#         # conn.commit()


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

    # Render org-branded content
    content = render_receipt_content(d["org_id"], d)
    subject = content["subject"]
    body_text = content["body_text"]
    body_html = content["body_html"]
    to_email = d["donor_email"]

    with get_db_connection() as conn, conn.cursor() as cur:
        # If already sent, stop (idempotent)
        cur.execute(
            "SELECT id, sent_at FROM email_receipts WHERE donation_id=%s",
            (donation_id,),
        )
        row = cur.fetchone()
        if row and row[1]:
            return

        if row:
            # Update existing skeleton row with rendered content
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
            # Fresh insert with rendered content
            cur.execute(
                """
                INSERT INTO email_receipts
                    (donation_id, to_email, subject, body_text, body_html, sent_at)
                VALUES (%s, %s, %s, %s, %s, now())
                """,
                (donation_id, to_email, subject, body_text, body_html),
            )
        conn.commit()

    # Dev log (still prints, but DB now stores the branded content)
    if DEV_EMAIL_LOG_ONLY:
        print(f"[email][dev] to={to_email} subj={subject}")
        print(body_text)
