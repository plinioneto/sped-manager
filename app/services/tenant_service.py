from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.utils.formatters import limpar_cnpj


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
        # sempre compara só os números
        cnpj_limpo = limpar_cnpj(cnpj)
        return (
            self.session.query(Tenant)
            .filter(Tenant.cnpj == cnpj_limpo)
            .first()
        )

    def criar(self, nome: str, cnpj: str):
        # salva sempre sem máscara
        tenant = Tenant(nome=nome, cnpj=limpar_cnpj(cnpj))
        self.session.add(tenant)
        self.session.commit()
        self.session.refresh(tenant)
        return tenant