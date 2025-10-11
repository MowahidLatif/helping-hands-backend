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
    "created_at",
    "updated_at",
]


def get_email_settings(org_id: str) -> Optional[Dict[str, Any]]:
    sql = f"SELECT {', '.join(COLS)} FROM org_email_settings WHERE org_id=%s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        row = cur.fetchone()
        return dict(zip(COLS, row)) if row else None


def upsert_email_settings(
    org_id: str,
    from_name: Optional[str] = None,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    bcc_to: Optional[str] = None,
    receipt_subject: Optional[str] = None,
    receipt_text: Optional[str] = None,
    receipt_html: Optional[str] = None,
) -> Dict[str, Any]:
    vals = [
        from_name,
        from_email,
        reply_to,
        bcc_to,
        receipt_subject,
        receipt_text,
        receipt_html,
    ]

    sql = """
    INSERT INTO org_email_settings (
      org_id, from_name, from_email, reply_to, bcc_to, receipt_subject, receipt_text, receipt_html
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (org_id) DO UPDATE SET
      from_name       = COALESCE(EXCLUDED.from_name,       org_email_settings.from_name),
      from_email      = COALESCE(EXCLUDED.from_email,      org_email_settings.from_email),
      reply_to        = COALESCE(EXCLUDED.reply_to,        org_email_settings.reply_to),
      bcc_to          = COALESCE(EXCLUDED.bcc_to,          org_email_settings.bcc_to),
      receipt_subject = COALESCE(EXCLUDED.receipt_subject, org_email_settings.receipt_subject),
      receipt_text    = COALESCE(EXCLUDED.receipt_text,    org_email_settings.receipt_text),
      receipt_html    = COALESCE(EXCLUDED.receipt_html,    org_email_settings.receipt_html),
      updated_at      = now()
    RETURNING org_id, from_name, from_email, reply_to, bcc_to, receipt_subject, receipt_text, receipt_html, created_at, updated_at;
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
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))
