from app.utils.db import get_session, engine
from app.models.base import Base
from app.models.tenant import Tenant

Base.metadata.create_all(bind=engine)

db = next(get_session())
tenants = db.query(Tenant).all()

for t in tenants:
    print(f"ID: {t.id} | Nome: {t.nome} | CNPJ: '{t.cnpj}'")