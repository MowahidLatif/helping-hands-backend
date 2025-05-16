from app.utils.db import get_db_connection

def insert_media(campaign_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO media (campaign_id, type, url, title, description)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """, (
        campaign_id,
        data['type'],
        data['url'],
        data.get('title'),
        data.get('description')
    ))
    media = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return media

def select_media_by_campaign(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM media
        WHERE campaign_id = %s
        ORDER BY uploaded_at DESC;
    """, (campaign_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
