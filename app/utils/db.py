from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sped_manager.db")

_is_sqlite = "sqlite" in DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
)

# WAL mode: permite leituras concorrentes enquanto uma escrita está em andamento.
# Elimina a maioria dos "database is locked" em uso com Streamlit (múltiplas
# sessões abertas simultaneamente no mesmo processo).
if _is_sqlite:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA busy_timeout=10000")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def upgrade_db():
    """Garante que todas as tabelas existam no banco.

    Usa create_all (idempotente — ignora tabelas já existentes).
    Migrações de schema são aplicadas manualmente via: alembic upgrade head
    """
    import app.models  # noqa: F401 — registra todos os models no Base
    from app.models.base import Base
    Base.metadata.create_all(bind=engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()