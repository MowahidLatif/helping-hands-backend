from typing import Any
from app.utils.db import get_db_connection
from psycopg2.extras import Json


def mark_event_processed(
    event_id: str, event_type: str, raw_event: dict[str, Any]
) -> bool:
    """
    Insert a row into stripe_events. Returns True if inserted, False if duplicate.
    Schema used (your current table):
      - event_id text PRIMARY KEY
      - type text NOT NULL
      - raw jsonb NOT NULL
      - created_at timestamptz NOT NULL DEFAULT now()
    """
    sql = """
    INSERT INTO stripe_events (event_id, type, raw)
    VALUES (%s, %s, %s)
    ON CONFLICT (event_id) DO NOTHING
    RETURNING event_id
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (event_id, event_type, Json(raw_event)))
        row = cur.fetchone()
        conn.commit()
        return row is not None
