import json
import psycopg2
import psycopg2.pool
import os
from dotenv import load_dotenv

load_dotenv()

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _fetch_secret_password() -> str | None:
    """
    Fetch the DB password from AWS Secrets Manager when DB_SECRET_NAME is set.
    RDS-managed secrets are JSON: {"username": "...", "password": "..."}
    Falls back to DB_PASSWORD if DB_SECRET_NAME is not set.
    """
    secret_name = os.getenv("DB_SECRET_NAME")
    if not secret_name:
        return None

    import boto3
    from botocore.exceptions import ClientError

    region = os.getenv("AWS_REGION", "us-east-2")
    client = boto3.session.Session().client(
        service_name="secretsmanager", region_name=region
    )
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise RuntimeError(f"Failed to fetch DB secret '{secret_name}': {e}") from e

    secret = json.loads(response["SecretString"])
    return secret["password"]


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("DATABASE_URL")
        minconn = int(os.getenv("DB_POOL_MIN", "2"))
        maxconn = int(os.getenv("DB_POOL_MAX", "10"))
        # SSL: default to "require" for RDS/cloud, "disable" for local dev.
        # Use "verify-full" + DB_SSLROOTCERT for maximum security (recommended for RDS).
        sslmode = os.getenv("DB_SSLMODE", "require")
        sslrootcert = os.getenv("DB_SSLROOTCERT")  # e.g. ./global-bundle.pem

        ssl_kwargs: dict = {"sslmode": sslmode}
        if sslrootcert:
            ssl_kwargs["sslrootcert"] = sslrootcert

        if url:
            if "sslmode=" not in url:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}sslmode={sslmode}"
                if sslrootcert and "sslrootcert=" not in url:
                    url = f"{url}&sslrootcert={sslrootcert}"
            _pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn=url)
        else:
            # Prefer Secrets Manager; fall back to DB_PASSWORD for local dev
            password = _fetch_secret_password() or os.getenv("DB_PASSWORD", "dev")
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn,
                maxconn,
                host=os.getenv("DB_HOST", "127.0.0.1"),
                database=os.getenv("DB_NAME", "donations_dev"),
                user=os.getenv("DB_USER", "dev"),
                password=password,
                port=os.getenv("DB_PORT", "65432"),
                **ssl_kwargs,
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
