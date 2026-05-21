from app.utils.db import get_db_connection


def create_waitlist_entry(first_name: str, last_name: str, email: str, phone: str | None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO waitlist (first_name, last_name, email, phone)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, created_at
                """,
                (first_name, last_name, email, phone),
            )
            conn.commit()
            return cur.fetchone()
    finally:
        conn.close()
