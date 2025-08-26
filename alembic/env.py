import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    from urllib.parse import quote_plus

    user = os.getenv("DB_USER", "dev")
    pwd = quote_plus(os.getenv("DB_PASSWORD", "dev"))
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "65432")
    name = os.getenv("DB_NAME", "donations_dev")
    # NOTE: psycopg2 to match your installed driver
    db_url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"

config.set_main_option("sqlalchemy.url", db_url)

target_metadata = None


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
