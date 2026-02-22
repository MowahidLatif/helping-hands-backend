from typing import Any, List, Dict, Optional
from app.utils.db import get_db_connection
from flask import render_template_string
from app.models.org_email_settings import get_email_settings
from app.models.campaign import get_campaign

DEFAULT_SUBJECT = "Thanks for your donation to {{ campaign.title }}!"
DEFAULT_TEXT = """Hi,

Thank you for your donation of ${{ amount }} to {{ campaign.title }}.
Campaign: {{ campaign.title }} (#{{ campaign.id }})
Currency: {{ donation.currency|upper }}

— The Team
"""
DEFAULT_HTML = """<p>Hi,</p>
<p>Thank you for your donation of ${{ amount }} to <strong>{{ campaign.title }}</strong>.</p>
<p>Campaign: {{ campaign.title }} (#{{ campaign.id }})<br/>
Currency: {{ donation.currency|upper }}</p>
<p>— The Team</p>
"""

# Winner notification template
# prize_amount: formatted string e.g. "$1,000.00" when prize set, else None
DEFAULT_WINNER_SUBJECT = "Congratulations! You won the {{ campaign.title }} giveaway!"
DEFAULT_WINNER_TEXT = """Hi,

Congratulations! You have been selected as the winner of the {{ campaign.title }} giveaway.{% if prize_amount %}

Your cash prize: {{ prize_amount }}{% endif %}

We'll be in touch shortly with details on how to claim your prize.

— The Team
"""
DEFAULT_WINNER_HTML = """<p>Hi,</p>
<p><strong>Congratulations!</strong> You have been selected as the winner of the {{ campaign.title }} giveaway.</p>{% if prize_amount %}
<p>Your cash prize: <strong>{{ prize_amount }}</strong></p>{% endif %}
<p>We'll be in touch shortly with details on how to claim your prize.</p>
<p>— The Team</p>
"""


def list_receipts_for_campaign(
    campaign_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    sql = """
      SELECT er.id, er.donation_id, er.to_email, er.subject, er.sent_at, er.created_at
      FROM email_receipts er
      JOIN donations d ON d.id = er.donation_id
      WHERE d.campaign_id = %s
      ORDER BY er.created_at DESC
      LIMIT %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, limit))
        rows = cur.fetchall()
        cols = ["id", "donation_id", "to_email", "subject", "sent_at", "created_at"]
        return [dict(zip(cols, r)) for r in rows]


def get_receipt(receipt_id: str) -> Optional[Dict[str, Any]]:
    sql = """
      SELECT
        er.id,
        d.org_id,
        d.campaign_id,
        er.donation_id,
        er.to_email,
        er.subject,
        er.body_html,
        er.sent_at,
        er.created_at
      FROM email_receipts er
      JOIN donations d ON d.id = er.donation_id
      WHERE er.id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (receipt_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "donation_id",
            "to_email",
            "subject",
            "body_html",
            "sent_at",
            "created_at",
        ]
        return dict(zip(cols, row))


def resend_receipt(receipt_id: str) -> Optional[Dict[str, Any]]:
    """
    Resend by updating the existing row (keep one row per donation).
    - Refresh sent_at.
    - Ensure body_text is non-NULL (derive from HTML if needed, then fallback).
    - Ensure body_html has a minimal fallback for preview/sanity.
    """
    sql = """
      WITH upd AS (
        UPDATE email_receipts er
        SET
          body_text = COALESCE(
            NULLIF(er.body_text, ''),
            NULLIF(regexp_replace(COALESCE(er.body_html, ''), E'<[^>]+>', '', 'g'), ''),
            'Thank you for your donation.'
          ),
          body_html = COALESCE(er.body_html, '<p>No content</p>'),
          sent_at   = now(),
          updated_at = now()
        WHERE er.id = %s
        RETURNING er.id, er.donation_id, er.to_email, er.subject, er.sent_at, er.created_at
      )
      SELECT * FROM upd
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (receipt_id,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        cols = ["id", "donation_id", "to_email", "subject", "sent_at", "created_at"]
        return dict(zip(cols, row))


def _format_amount(cents: int) -> str:
    if cents is None:
        return "0.00"
    return f"{cents/100:.2f}"


def render_receipt_content(org_id: str, donation_row: Dict[str, Any]) -> Dict[str, str]:
    camp = get_campaign(donation_row["campaign_id"]) or {}
    org_cfg = get_email_settings(org_id) or {}
    subject_tpl = org_cfg.get("receipt_subject") or DEFAULT_SUBJECT
    text_tpl = org_cfg.get("receipt_text") or DEFAULT_TEXT
    html_tpl = org_cfg.get("receipt_html") or DEFAULT_HTML

    ctx = {
        "org": {"id": org_id},
        "campaign": {"id": camp.get("id"), "title": camp.get("title", "Our campaign")},
        "donation": {
            "id": donation_row["id"],
            "currency": donation_row.get("currency", "usd"),
        },
        "amount": _format_amount(int(donation_row.get("amount_cents") or 0)),
        "donor_email": donation_row.get("donor_email"),
    }

    subject = render_template_string(subject_tpl, **ctx)
    body_text = render_template_string(text_tpl, **ctx)
    body_html = render_template_string(html_tpl, **ctx)
    return {"subject": subject, "body_text": body_text, "body_html": body_html}


def render_winner_content(
    org_id: str,
    campaign_title: str,
    winner_email: Optional[str] = None,
    prize_cents: Optional[int] = None,
) -> Dict[str, str]:
    org_cfg = get_email_settings(org_id) or {}
    subject_tpl = org_cfg.get("winner_subject") or DEFAULT_WINNER_SUBJECT
    text_tpl = org_cfg.get("winner_text") or DEFAULT_WINNER_TEXT
    html_tpl = org_cfg.get("winner_html") or DEFAULT_WINNER_HTML
    prize_amount = None
    if prize_cents is not None and prize_cents > 0:
        prize_amount = _format_amount(prize_cents)
    ctx = {
        "org": {"id": org_id},
        "campaign": {"title": campaign_title},
        "winner_email": winner_email,
        "prize_amount": prize_amount,
    }
    return {
        "subject": render_template_string(subject_tpl, **ctx),
        "body_text": render_template_string(text_tpl, **ctx),
        "body_html": render_template_string(html_tpl, **ctx),
    }
