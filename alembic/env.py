import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from app.utils.secrets import get_secret_or_env

load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_password() -> str:
    """Fetch DB password using the same AWS-first path as runtime DB connections."""
    return get_secret_or_env(
        "DB_PASSWORD",
        secret_name_env="DB_SECRET_NAME",
        json_keys=("password",),
    ) or "dev"


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
