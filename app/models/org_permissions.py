"""Per-user permissions for an org. Owner/admin have all permissions implicitly."""

from typing import List
from app.utils.db import get_db_connection

# Fixed list of permission codes (keep in sync with frontend)
ALL_PERMISSIONS = [
    "campaign:create",
    "campaign:edit",
    "campaign:delete",
    "tasks:create",
    "tasks:assign",
    "tasks:edit_any",
]


def get_member_permissions(org_id: str, user_id: str) -> List[str]:
    sql = """
    SELECT permission FROM org_user_permissions
    WHERE org_id = %s AND user_id = %s
    ORDER BY permission
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, user_id))
        return [r[0] for r in cur.fetchall()]


def set_member_permissions(org_id: str, user_id: str, permissions: List[str]) -> None:
    valid = [p for p in permissions if p in ALL_PERMISSIONS]
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM org_user_permissions WHERE org_id = %s AND user_id = %s",
            (org_id, user_id),
        )
        for p in valid:
            cur.execute(
                "INSERT INTO org_user_permissions (org_id, user_id, permission) VALUES (%s, %s, %s)",
                (org_id, user_id, p),
            )
        conn.commit()


def user_has_permission(user_id: str, org_id: str, permission: str, role: str) -> bool:
    """Owner and admin have all permissions. Otherwise check org_user_permissions."""
    if role in ("owner", "admin"):
        return True
    perms = get_member_permissions(org_id, user_id)
    return permission in perms


def get_all_members_permissions(org_id: str) -> dict:
    """Return {user_id: [permission, ...]} for all members in org."""
    sql = """
    SELECT user_id, permission FROM org_user_permissions WHERE org_id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        out = {}
        for r in cur.fetchall():
            uid = str(r[0])
            if uid not in out:
                out[uid] = []
            out[uid].append(r[1])
        return out
