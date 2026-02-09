import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """
    Connect to PostgreSQL. Uses DATABASE_URL if set (e.g. for AWS RDS);
    otherwise falls back to DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        database=os.getenv("DB_NAME", "donations_dev"),
        user=os.getenv("DB_USER", "dev"),
        password=os.getenv("DB_PASSWORD", "dev"),
        port=os.getenv("DB_PORT", "65432"),
    )
