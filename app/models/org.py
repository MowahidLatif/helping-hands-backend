from typing import Dict, Any
from app.utils.db import get_db_connection


def create_organization(name: str) -> Dict[str, Any]:
    sql = "INSERT INTO organizations (name) VALUES (%s) RETURNING id, name"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (name,))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "name": row[1]}
