from sqlalchemy.orm import Session
from app.models.tenant import Tenant

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

    def criar(self, nome: str, cnpj: str):
        tenant = Tenant(nome=nome, cnpj=cnpj)
        self.session.add(tenant)
        self.session.commit()
        self.session.refresh(tenant)
        return tenant