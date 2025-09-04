from app.utils.db import get_db_connection
from typing import Optional, Dict, Any


# Replace or modify to fit the formatting of other code (03/09/2025)
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    sql = "SELECT id, email, password_hash, name FROM users WHERE email = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (email,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "password_hash": row[2], "name": row[3]}


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


def update_password(user_id, new_password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET password_hash = %s
        WHERE id = %s;
    """,
        (new_password, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()
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


# def get_user_by_email(email):
#     conn = get_db_connection()
#     cur = conn.cursor()
#     cur.execute("SELECT id, username, email, custom_domain FROM users WHERE email = %s;", (email,))
#     user = cur.fetchone()
#     cur.close()
#     conn.close()
#     return user
