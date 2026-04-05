import psycopg2
import psycopg2.pool
import os
from dotenv import load_dotenv

load_dotenv()

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("DATABASE_URL")
        minconn = int(os.getenv("DB_POOL_MIN", "2"))
        maxconn = int(os.getenv("DB_POOL_MAX", "10"))
        if url:
            _pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn=url)
        else:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn,
                maxconn,
                host=os.getenv("DB_HOST", "127.0.0.1"),
                database=os.getenv("DB_NAME", "donations_dev"),
                user=os.getenv("DB_USER", "dev"),
                password=os.getenv("DB_PASSWORD", "dev"),
                port=os.getenv("DB_PORT", "65432"),
            )
    return _pool


class _PooledConnection:
    """Wraps a psycopg2 connection and returns it to the pool on close()."""

    def __init__(self, conn):
        object.__setattr__(self, "_conn", conn)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def close(self):
        _get_pool().putconn(object.__getattribute__(self, "_conn"))


def get_db_connection() -> _PooledConnection:
    """
    Get a pooled connection to PostgreSQL.
    Call conn.close() when done to return it to the pool.
    Uses DB_POOL_MIN (default 2) and DB_POOL_MAX (default 10) env vars.
    """
    conn = _get_pool().getconn()
    return _PooledConnection(conn)
