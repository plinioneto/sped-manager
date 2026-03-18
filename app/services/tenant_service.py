from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.utils.formatters import formatar_cnpj, limpar_cnpj

class TenantService:
    def __init__(self, session: Session):
        self.session = session

    def listar(self):
        return self.session.query(Tenant).filter(Tenant.ativo == True).all()

    def buscar_por_id(self, tenant_id: int):
        return (
            self.session.query(Tenant)
            .filter(Tenant.id == tenant_id)
            .first()
        )
    
    def buscar_por_cnpj(self, cnpj: str):
        # normaliza o CNPJ antes de buscar — aceita com ou sem formatação
        cnpj_limpo = limpar_cnpj(cnpj)
        tenants = self.listar()
        return next(
            (t for t in tenants if limpar_cnpj(t.cnpj) == cnpj_limpo),
            None
        )

    def criar(self, nome: str, cnpj: str):
        # sempre salva o CNPJ formatado
        tenant = Tenant(nome=nome, cnpj=formatar_cnpj(cnpj))
        self.session.add(tenant)
        self.session.commit()
        self.session.refresh(tenant)
        return tenant