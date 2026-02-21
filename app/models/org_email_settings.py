from typing import Any, Dict, Optional
from app.utils.db import get_db_connection

COLS = [
    "org_id",
    "from_name",
    "from_email",
    "reply_to",
    "bcc_to",
    "receipt_subject",
    "receipt_text",
    "receipt_html",
    "thank_you_subject",
    "thank_you_text",
    "thank_you_html",
    "winner_subject",
    "winner_text",
    "winner_html",
    "created_at",
    "updated_at",
]


def get_email_settings(org_id: str) -> Optional[Dict[str, Any]]:
    cols = [
        "org_id",
        "from_name",
        "from_email",
        "reply_to",
        "bcc_to",
        "receipt_subject",
        "receipt_text",
        "receipt_html",
        "thank_you_subject",
        "thank_you_text",
        "thank_you_html",
        "winner_subject",
        "winner_text",
        "winner_html",
        "created_at",
        "updated_at",
    ]
    sql = f"SELECT {', '.join(cols)} FROM org_email_settings WHERE org_id=%s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(zip(cols, row))


def upsert_email_settings(
    org_id: str,
    from_name: Optional[str] = None,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    bcc_to: Optional[str] = None,
    receipt_subject: Optional[str] = None,
    receipt_text: Optional[str] = None,
    receipt_html: Optional[str] = None,
    thank_you_subject: Optional[str] = None,
    thank_you_text: Optional[str] = None,
    thank_you_html: Optional[str] = None,
    winner_subject: Optional[str] = None,
    winner_text: Optional[str] = None,
    winner_html: Optional[str] = None,
    **_ignored: Any,
) -> Dict[str, Any]:
    vals = [
        from_name,
        from_email,
        reply_to,
        bcc_to,
        receipt_subject,
        receipt_text,
        receipt_html,
        thank_you_subject,
        thank_you_text,
        thank_you_html,
        winner_subject,
        winner_text,
        winner_html,
    ]

    sql = """
    INSERT INTO org_email_settings (
      org_id, from_name, from_email, reply_to, bcc_to,
      receipt_subject, receipt_text, receipt_html,
      thank_you_subject, thank_you_text, thank_you_html,
      winner_subject, winner_text, winner_html
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (org_id) DO UPDATE SET
      from_name         = COALESCE(EXCLUDED.from_name,         org_email_settings.from_name),
      from_email        = COALESCE(EXCLUDED.from_email,        org_email_settings.from_email),
      reply_to          = COALESCE(EXCLUDED.reply_to,          org_email_settings.reply_to),
      bcc_to            = COALESCE(EXCLUDED.bcc_to,            org_email_settings.bcc_to),
      receipt_subject   = COALESCE(EXCLUDED.receipt_subject,   org_email_settings.receipt_subject),
      receipt_text      = COALESCE(EXCLUDED.receipt_text,      org_email_settings.receipt_text),
      receipt_html      = COALESCE(EXCLUDED.receipt_html,      org_email_settings.receipt_html),
      thank_you_subject = COALESCE(EXCLUDED.thank_you_subject, org_email_settings.thank_you_subject),
      thank_you_text    = COALESCE(EXCLUDED.thank_you_text,    org_email_settings.thank_you_text),
      thank_you_html    = COALESCE(EXCLUDED.thank_you_html,    org_email_settings.thank_you_html),
      winner_subject    = COALESCE(EXCLUDED.winner_subject,    org_email_settings.winner_subject),
      winner_text       = COALESCE(EXCLUDED.winner_text,       org_email_settings.winner_text),
      winner_html       = COALESCE(EXCLUDED.winner_html,       org_email_settings.winner_html),
      updated_at        = now()
    RETURNING
      org_id, from_name, from_email, reply_to, bcc_to,
      receipt_subject, receipt_text, receipt_html,
      thank_you_subject, thank_you_text, thank_you_html,
      winner_subject, winner_text, winner_html,
      created_at, updated_at;
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, [org_id, *vals])
        row = cur.fetchone()
        conn.commit()
        cols = [
            "org_id",
            "from_name",
            "from_email",
            "reply_to",
            "bcc_to",
            "receipt_subject",
            "receipt_text",
            "receipt_html",
            "thank_you_subject",
            "thank_you_text",
            "thank_you_html",
            "winner_subject",
            "winner_text",
            "winner_html",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))
