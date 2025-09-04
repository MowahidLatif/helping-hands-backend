from typing import Optional, Tuple
from typing import List, Dict, Any
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


def get_user_role_in_org(user_id: str, org_id: str) -> Optional[str]:
    sql = "SELECT role FROM org_users WHERE org_id = %s AND user_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, user_id))
        row = cur.fetchone()
        return row[0] if row else None


def list_org_members(org_id: str) -> List[Dict[str, Any]]:
    sql = """
      SELECT u.id, u.email, u.name, ou.role
      FROM org_users ou JOIN users u ON u.id = ou.user_id
      WHERE ou.org_id = %s
      ORDER BY u.email
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        return [
            {"id": r[0], "email": r[1], "name": r[2], "role": r[3]}
            for r in cur.fetchall()
        ]


def set_user_role(org_id: str, user_id: str, role: str) -> bool:
    sql = "UPDATE org_users SET role = %s WHERE org_id = %s AND user_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (role, org_id, user_id))
        conn.commit()
        return cur.rowcount > 0


def remove_user_from_org(org_id: str, user_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM org_users WHERE org_id = %s AND user_id = %s",
            (org_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
