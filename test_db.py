from app.utils.db import get_db_connection

conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT version()")
print(cur.fetchone())
conn.close()
print("Connection successful.")
