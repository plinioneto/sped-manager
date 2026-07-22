"""
Rotas do módulo do Consultor — todas exigem Depends(get_consultor).

GET    /consultor/perfil       → dados de marca do consultor + contador de clientes ativos
GET    /consultor/dashboard    → contadores (clientes, clientes ativos, produtos ativos entre os clientes)
GET    /consultor/clientes     → lista clientes vinculados ao consultor
POST   /consultor/clientes     → cria cliente vinculado ao consultor (usuário de login opcional)
PUT    /consultor/clientes/{id} → atualiza cliente (só se pertencer ao consultor)
DELETE /consultor/clientes/{id} → desativa cliente (só se pertencer ao consultor)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.consultor import Consultor
from app.models.tenant_produto_saas import TenantProdutoSaas
from app.services.tenant_service import TenantService
from app.utils.formatters import limpar_cnpj
from api.auth import hash_senha
from api.deps import get_db, get_consultor

router = APIRouter(prefix="/consultor", tags=["consultor"], dependencies=[Depends(get_consultor)])


class ConsultorPerfilOut(BaseModel):
    id: int
    nome: str
    cnpj: str | None
    telefone: str | None
    logo_url: str | None
    slogan: str | None
    cor_primaria: str | None
    cor_secundaria: str | None
    clientes_ativos: int


class ConsultorDashboardOut(BaseModel):
    total_clientes: int
    clientes_ativos: int
    produtos_ativos: int


class ClienteOut(BaseModel):
    tenant_id: int
    nome: str
    cnpj: str
    ativo: bool


class ClienteCreateRequest(BaseModel):
    nome: str
    cnpj: str
    usuario_login: str | None = None
    usuario_senha: str | None = None
    usuario_nome: str | None = None


class ClienteUpdateRequest(BaseModel):
    nome: str | None = None
    cnpj: str | None = None
    ativo: bool | None = None


@router.get("/perfil", response_model=ConsultorPerfilOut)
def perfil(consultor: Consultor = Depends(get_consultor), db: Session = Depends(get_db)):
    clientes_ativos = (
        db.query(Tenant)
        .filter(Tenant.consultor_id == consultor.id, Tenant.ativo == True)
        .count()
    )
    return ConsultorPerfilOut(
        id=consultor.id,
        nome=consultor.nome,
        cnpj=consultor.cnpj,
        telefone=consultor.telefone,
        logo_url=consultor.logo_url,
        slogan=consultor.slogan,
        cor_primaria=consultor.cor_primaria,
        cor_secundaria=consultor.cor_secundaria,
        clientes_ativos=clientes_ativos,
    )


@router.get("/dashboard", response_model=ConsultorDashboardOut)
def dashboard(consultor: Consultor = Depends(get_consultor), db: Session = Depends(get_db)):
    clientes = db.query(Tenant).filter(Tenant.consultor_id == consultor.id).all()
    clientes_ids = [c.id for c in clientes]
    produtos_ativos = (
        db.query(TenantProdutoSaas)
        .filter(TenantProdutoSaas.tenant_id.in_(clientes_ids), TenantProdutoSaas.ativo == True)
        .count()
        if clientes_ids
        else 0
    )
    return ConsultorDashboardOut(
        total_clientes=len(clientes),
        clientes_ativos=sum(1 for c in clientes if c.ativo),
        produtos_ativos=produtos_ativos,
    )


@router.get("/clientes", response_model=list[ClienteOut])
def listar_clientes(consultor: Consultor = Depends(get_consultor), db: Session = Depends(get_db)):
    clientes = (
        db.query(Tenant)
        .filter(Tenant.consultor_id == consultor.id)
        .order_by(Tenant.nome)
        .all()
    )
    return [ClienteOut(tenant_id=c.id, nome=c.nome, cnpj=c.cnpj, ativo=c.ativo) for c in clientes]


@router.post("/clientes", response_model=ClienteOut, status_code=201)
def criar_cliente(
    body: ClienteCreateRequest,
    consultor: Consultor = Depends(get_consultor),
    db: Session = Depends(get_db),
):
    if db.query(Tenant).filter(Tenant.cnpj == limpar_cnpj(body.cnpj)).first():
        raise HTTPException(status_code=400, detail="CNPJ já cadastrado")

    if body.usuario_login and db.query(Usuario).filter(Usuario.login == body.usuario_login.strip()).first():
        raise HTTPException(status_code=400, detail="Login já cadastrado")

    tenant = TenantService(db).criar(body.nome, body.cnpj, consultor_id=consultor.id)

    if body.usuario_login and body.usuario_senha:
        usuario = Usuario(
            tenant_id=tenant.id,
            login=body.usuario_login.strip(),
            senha_hash=hash_senha(body.usuario_senha),
            nome=body.usuario_nome or tenant.nome,
            role="cliente",
        )
        db.add(usuario)
        db.commit()

    return ClienteOut(tenant_id=tenant.id, nome=tenant.nome, cnpj=tenant.cnpj, ativo=tenant.ativo)


@router.put("/clientes/{tenant_id}", response_model=ClienteOut)
def atualizar_cliente(
    tenant_id: int,
    body: ClienteUpdateRequest,
    consultor: Consultor = Depends(get_consultor),
    db: Session = Depends(get_db),
):
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == tenant_id, Tenant.consultor_id == consultor.id)
        .first()
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if body.nome is not None:
        tenant.nome = body.nome
    if body.cnpj is not None:
        tenant.cnpj = body.cnpj
    if body.ativo is not None:
        tenant.ativo = body.ativo
    db.commit()

    return ClienteOut(tenant_id=tenant.id, nome=tenant.nome, cnpj=tenant.cnpj, ativo=tenant.ativo)


@router.delete("/clientes/{tenant_id}", status_code=204)
def desativar_cliente(
    tenant_id: int,
    consultor: Consultor = Depends(get_consultor),
    db: Session = Depends(get_db),
):
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == tenant_id, Tenant.consultor_id == consultor.id)
        .first()
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    tenant.ativo = False
    db.commit()
