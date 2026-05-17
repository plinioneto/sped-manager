import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Lê DATABASE_URL via db.py para garantir que st.secrets seja aplicado
# (necessário no Streamlit Cloud, onde não há .env)
from app.utils.db import DATABASE_URL  # noqa: E402
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Importa todos os models para que o metadata esteja completo
import app.models  # noqa: F401 — registra todos os models no Base

from app.models.base import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    is_sqlite = "sqlite" in url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    is_sqlite = "sqlite" in config.get_main_option("sqlalchemy.url")
    connect_args = {"check_same_thread": False} if is_sqlite else {}

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
