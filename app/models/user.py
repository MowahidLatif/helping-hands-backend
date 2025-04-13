from app.utils.db import get_db_connection

def get_all_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email FROM users;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
