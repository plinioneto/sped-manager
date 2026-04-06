from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite::///./sped_manager.db")

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


def run_migrations():
    """Migrações idempotentes — executadas em todo ponto de entrada da app."""
    from sqlalchemy import text
    # SQLite não suporta constraints em ALTER TABLE ADD COLUMN — UNIQUE é ignorado aqui
    # e garantido pelo ORM/índice criado a seguir
    _migrations = [
        "ALTER TABLE tenants ADD COLUMN grupo_id INTEGER REFERENCES grupos_empresariais(id)",
        "ALTER TABLE tenants ADD COLUMN senha_hash TEXT",
        "ALTER TABLE tenants ADD COLUMN codigo_acesso TEXT",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_codigo_acesso ON tenants(codigo_acesso)",
    ]
    with engine.connect() as conn:
        for sql in _migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # coluna já existe


def get_session():
    db = SessionLocal()
    try:
        yield db
    
    finally:
        db.close()