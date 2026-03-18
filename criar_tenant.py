from app.utils.db import get_session, engine
from app.models.base import Base
from app.models import tenant  # garante que o model é carregado
from app.services.tenant_service import TenantService

# cria as tabelas no banco
Base.metadata.create_all(bind=engine)

db = next(get_session())
service = TenantService(db)

tenant = service.criar(
    nome="Supermercado Teste",
    cnpj="00.000.000/0001-00"
)

print(f"Tenant criado: {tenant.id} - {tenant.nome}")