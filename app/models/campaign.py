from app.utils.db import get_db_connection

def insert_campaign(data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO campaigns (user_id, title, slug, description, goal_amount)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """, (data['user_id'], data['title'], data['slug'], data.get('description'), data.get('goal_amount')))
    campaign = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return campaign

def select_campaigns():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM campaigns ORDER BY created_at DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def update_campaign_data(campaign_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE campaigns
        SET title = %s, description = %s, is_completed = %s, goal_amount = %s
        WHERE id = %s
        RETURNING *;
    """, (data['title'], data['description'], data['is_completed'], data['goal_amount'], campaign_id))
    campaign = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return campaign

def delete_campaign_by_id(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM campaigns WHERE id = %s;", (campaign_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}
