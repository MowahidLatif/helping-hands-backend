from app.utils.db import get_db_connection

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
    cur.execute("""
        INSERT INTO users (username, email, password_hash, custom_domain)
        VALUES (%s, %s, %s, %s)
        RETURNING id, username, email;
    """, (data['username'], data['email'], data['password_hash'], data.get('custom_domain')))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user

def update_user_data(user_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET username = %s, email = %s, custom_domain = %s
        WHERE id = %s
        RETURNING id, username, email;
    """, (data['username'], data['email'], data.get('custom_domain'), user_id))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user

def update_password(user_id, new_password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET password_hash = %s
        WHERE id = %s;
    """, (new_password, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "password updated"}

def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, custom_domain FROM users WHERE id = %s;", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user
