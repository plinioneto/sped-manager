from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from app.utils.db import engine

Base = declarative_base()

def init_db():
    from app.models import tenant, produto, documento_fiscal, icms_c190
    Base.metadata.create_all(bind=engine)