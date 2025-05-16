from app.utils.db import get_db_connection

def insert_donation(data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO donations (campaign_id, donor_name, donor_email, amount, message)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """, (
        data['campaign_id'],
        data.get('donor_name'),
        data.get('donor_email'),
        data['amount'],
        data.get('message')
    ))
    donation = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return donation

def select_donations_by_campaign(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM donations
        WHERE campaign_id = %s
        ORDER BY donated_at DESC;
    """, (campaign_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
