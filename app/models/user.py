from app.utils.db import get_db_connection
from typing import Optional, Dict, Any


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    sql = "SELECT id, email, password_hash, name FROM users WHERE email = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (email,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "password_hash": row[2], "name": row[3]}


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Return user row (id, email, password_hash, name) for auth schema. Used for password verify."""
    sql = "SELECT id, email, password_hash, name FROM users WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "email": row[1],
            "password_hash": row[2],
            "name": row[3],
        }


def create_user(
    email: str, password_hash: str, name: Optional[str] = None
) -> Dict[str, Any]:
    sql = """
    INSERT INTO users (email, password_hash, name)
    VALUES (%s, %s, %s)
    RETURNING id, email, name
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (email, password_hash, name))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "email": row[1], "name": row[2]}


def get_all_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email FROM users;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def insert_user(data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (username, email, password_hash, custom_domain)
        VALUES (%s, %s, %s, %s)
        RETURNING id, username, email;
    """,
        (
            data["username"],
            data["email"],
            data["password_hash"],
            data.get("custom_domain"),
        ),
    )
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user


def update_user_data(user_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET username = %s, email = %s, custom_domain = %s
        WHERE id = %s
        RETURNING id, username, email;
    """,
        (data["username"], data["email"], data.get("custom_domain"), user_id),
    )
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user


def update_password(user_id, new_password_hash: str):
    """Set user password_hash. Caller must pass already-hashed password."""
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
            (new_password_hash, user_id),
        )
        conn.commit()
    return {"status": "password updated"}


def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, email, custom_domain FROM users WHERE id = %s;",
        (user_id,),
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def get_user_profile_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Return public profile (id, email, name) for settings. Uses auth schema (name, email)."""
    sql = "SELECT id, email, name FROM users WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": str(row[0]), "email": row[1] or "", "name": row[2] or ""}


def update_user_profile(
    user_id: str, name: Optional[str] = None, email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update name and/or email. Email must be unique if provided.
    Returns updated profile dict or raises ValueError with message.
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        if email is not None:
            email_norm = (email or "").strip().lower()
            cur.execute(
                "SELECT id FROM users WHERE email = %s AND id != %s",
                (email_norm, user_id),
            )
            if cur.fetchone():
                raise ValueError("Email already in use")
            email = email_norm
        updates = []
        params = []
        if name is not None:
            updates.append("name = %s")
            params.append((name or "").strip() or None)
        if email is not None:
            updates.append("email = %s")
            params.append(email)
        if not updates:
            cur.execute("SELECT id, email, name FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return {"id": str(row[0]), "email": row[1] or "", "name": row[2] or ""}
        params.append(user_id)
        cur.execute(
            f"UPDATE users SET {', '.join(updates)}, updated_at = now() WHERE id = %s RETURNING id, email, name",
            params,
        )
        row = cur.fetchone()
        conn.commit()
        return {"id": str(row[0]), "email": row[1] or "", "name": row[2] or ""}
