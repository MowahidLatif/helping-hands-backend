from typing import Any
from app.utils.db import get_db_connection
from app.utils.slug import slugify as _slugify
import secrets


def create_organization(name: str, subdomain: str | None = None):
    sub = _slugify(subdomain or name) or f"org-{secrets.token_hex(3)}"

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO organizations (name, subdomain) VALUES (%s, %s) "
            "RETURNING id, name, subdomain",
            (name, sub),
        )
        row = cur.fetchone()
        conn.commit()

    return {"id": row[0], "name": row[1], "subdomain": row[2]}


def get_organization(org_id: str) -> dict[str, Any] | None:
    sql = "SELECT id, name, created_at, updated_at FROM organizations WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "updated_at": row[3],
        }


def list_user_organizations(user_id: str) -> list[dict[str, Any]]:
    sql = """
      SELECT o.id, o.name, ou.role
      FROM organizations o
      JOIN org_users ou ON ou.org_id = o.id
      WHERE ou.user_id = %s
      ORDER BY o.created_at ASC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        return [{"id": r[0], "name": r[1], "role": r[2]} for r in cur.fetchall()]


def update_organization_name(org_id: str, name: str) -> dict[str, Any] | None:
    sql = "UPDATE organizations SET name = %s, updated_at = now() WHERE id = %s RETURNING id, name"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (name, org_id))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "name": row[1]} if row else None


def delete_organization(org_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM organizations WHERE id = %s", (org_id,))
        conn.commit()
        return cur.rowcount > 0
