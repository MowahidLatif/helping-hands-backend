import json
import os
from logging.config import fileConfig
from urllib.parse import quote_plus

import boto3
from alembic import context
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_password() -> str:
    """Fetch password from AWS Secrets Manager if DB_SECRET_NAME is set, else use DB_PASSWORD."""
    secret_name = os.getenv("DB_SECRET_NAME")
    if secret_name:
        region = os.getenv("AWS_REGION", "us-east-2")
        client = boto3.session.Session().client(
            service_name="secretsmanager", region_name=region
        )
        try:
            response = client.get_secret_value(SecretId=secret_name)
            return json.loads(response["SecretString"])["password"]
        except ClientError as e:
            raise RuntimeError(f"Failed to fetch DB secret '{secret_name}': {e}") from e
    return os.getenv("DB_PASSWORD", "dev")


def _build_url() -> str:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    user = os.getenv("DB_USER", "dev")
    pwd = quote_plus(_get_password())
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "65432")
    name = os.getenv("DB_NAME", "donations_dev")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"


def _ssl_connect_args() -> dict:
    sslmode = os.getenv("DB_SSLMODE", "require")
    args: dict = {"sslmode": sslmode}
    sslrootcert = os.getenv("DB_SSLROOTCERT")
    if sslrootcert:
        args["sslrootcert"] = sslrootcert
    return args


target_metadata = None


def run_migrations_offline() -> None:
    context.configure(url=_build_url())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        _build_url(),
        poolclass=pool.NullPool,
        connect_args=_ssl_connect_args(),
    )
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
