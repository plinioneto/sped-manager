import bcrypt
from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.models.grupo_empresarial import GrupoEmpresarial
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

    def autenticar(self, identificador: str, senha: str):
        """Tenta código curto primeiro, depois CNPJ. Retorna Tenant ou None."""
        identificador = identificador.strip()
        tenant = (
            self.session.query(Tenant)
            .filter(Tenant.codigo_acesso == identificador, Tenant.ativo == True)
            .first()
        )
        if not tenant:
            cnpj_limpo = limpar_cnpj(identificador)
            tenant = (
                self.session.query(Tenant)
                .filter(Tenant.cnpj == cnpj_limpo, Tenant.ativo == True)
                .first()
            )
        if not tenant or not tenant.senha_hash:
            return None
        if bcrypt.checkpw(senha.encode("utf-8"), tenant.senha_hash.encode("utf-8")):
            return tenant
        return None

    def definir_senha(self, tenant_id: int, senha: str):
        tenant = self.buscar_por_id(tenant_id)
        if tenant:
            hashed = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
            tenant.senha_hash = hashed.decode("utf-8")
            self.session.commit()

    def criar(self, nome: str, cnpj: str, senha: str | None = None, codigo_acesso: str | None = None):
        # salva sempre sem máscara
        tenant = Tenant(
            nome=nome,
            cnpj=limpar_cnpj(cnpj),
            codigo_acesso=codigo_acesso.strip() if codigo_acesso else None,
        )
        if senha:
            hashed = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
            tenant.senha_hash = hashed.decode("utf-8")
        self.session.add(tenant)
        self.session.commit()
        self.session.refresh(tenant)
        return tenant

    # ── Grupos Empresariais ───────────────────────────────────────────────────

    def listar_grupos(self):
        return (
            self.session.query(GrupoEmpresarial)
            .filter(GrupoEmpresarial.ativo == True)
            .order_by(GrupoEmpresarial.nome)
            .all()
        )

    def criar_grupo(self, nome: str) -> GrupoEmpresarial:
        grupo = GrupoEmpresarial(nome=nome.strip())
        self.session.add(grupo)
        self.session.commit()
        self.session.refresh(grupo)
        return grupo

    def associar_tenant_a_grupo(self, tenant_id: int, grupo_id: int):
        tenant = self.buscar_por_id(tenant_id)
        if tenant:
            tenant.grupo_id = grupo_id
            self.session.commit()

    def tenants_do_grupo(self, grupo_id: int):
        return (
            self.session.query(Tenant)
            .filter(Tenant.grupo_id == grupo_id, Tenant.ativo == True)
            .order_by(Tenant.nome)
            .all()
        )

    def buscar_grupo_por_cnpj(self, cnpj: str):
        tenant = self.buscar_por_cnpj(cnpj)
        if tenant and tenant.grupo_id:
            return (
                self.session.query(GrupoEmpresarial)
                .filter(GrupoEmpresarial.id == tenant.grupo_id)
                .first()
            )
        return None