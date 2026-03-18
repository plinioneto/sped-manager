from app.utils.db import get_session, engine
from app.models.base import Base

# importa todos os models antes de criar as tabelas
from app.models.tenant import Tenant
from app.models.produto import Produto
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.arquivo_importado import ArquivoImportado

from app.services.tenant_service import TenantService
from app.utils.formatters import formatar_cnpj

# cria todas as tabelas
Base.metadata.create_all(bind=engine)

db = next(get_session())
service = TenantService(db)

tenant = service.criar(
    nome="Supermercado Teste",
    cnpj="00.000.000/0001-00"
)

print(f"Tenant criado: {tenant.id} - {tenant.nome}")