from typing import Optional, Tuple
from app.utils.db import get_db_connection


def add_user_to_org(org_id: str, user_id: str, role: str = "owner") -> None:
    sql = """
    INSERT INTO org_users (org_id, user_id, role)
    VALUES (%s, %s, %s)
    ON CONFLICT (org_id, user_id) DO NOTHING
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, user_id, role))
        conn.commit()


def get_primary_org_role(user_id: str) -> Optional[Tuple[str, str]]:
    """
    Returns (org_id, role) with a simple priority: owner > admin > member.
    """
    sql = """
    SELECT org_id, role
    FROM org_users
    WHERE user_id = %s
    ORDER BY CASE role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END
    LIMIT 1
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        return (row[0], row[1]) if row else None
