"""
Rotas do módulo de administração — todas exigem Depends(get_admin).

GET  /admin/clientes                             → lista de tenants + entitlement por produto
POST /admin/clientes                             → cria cliente (usuário de login opcional)
PUT  /admin/clientes/{tenant_id}                 → atualiza cliente (nome/cnpj/ativo/consultor)
GET  /admin/produtos                             → catálogo de produtos SaaS
PUT  /admin/clientes/{tenant_id}/produtos/{produto_id} → ativa/desativa produto para o tenant
PUT  /admin/usuarios/{usuario_id}/senha          → admin reseta senha de qualquer usuário
GET  /admin/consultores                          → lista consultores
POST /admin/consultores                          → cria consultor + usuário de login
PUT  /admin/consultores/{consultor_id}           → atualiza consultor
DELETE /admin/consultores/{consultor_id}         → desativa consultor
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.consultor import Consultor
from app.models.produto_saas import ProdutoSaas
from app.models.tenant_produto_saas import TenantProdutoSaas
from app.services.tenant_service import TenantService
from app.utils.formatters import limpar_cnpj
from api.auth import hash_senha
from api.deps import get_db, get_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_admin)])


class ProdutoEntitlementOut(BaseModel):
    produto_saas_id: int
    slug: str
    nome: str
    ativo: bool


class ClienteOut(BaseModel):
    tenant_id: int
    nome: str
    cnpj: str
    ativo: bool
    consultor_id: int | None
    consultor_nome: str | None
    produtos: list[ProdutoEntitlementOut]


class ProdutoSaasOut(BaseModel):
    id: int
    slug: str
    nome: str
    descricao: str | None
    ativo: bool

    class Config:
        from_attributes = True


class EntitlementRequest(BaseModel):
    ativo: bool


class SenhaResetRequest(BaseModel):
    nova_senha: str


class ClienteCreateRequest(BaseModel):
    nome: str
    cnpj: str
    consultor_id: int | None = None
    usuario_login: str | None = None
    usuario_senha: str | None = None
    usuario_nome: str | None = None


class ClienteUpdateRequest(BaseModel):
    nome: str | None = None
    cnpj: str | None = None
    ativo: bool | None = None
    consultor_id: int | None = None
    limpar_consultor: bool = False


class ConsultorOut(BaseModel):
    id: int
    nome: str
    cnpj: str | None
    telefone: str | None
    logo_url: str | None
    slogan: str | None
    cor_primaria: str | None
    cor_secundaria: str | None
    ativo: bool
    total_clientes: int


class ConsultorCreateRequest(BaseModel):
    nome: str
    usuario_login: str
    usuario_senha: str
    cnpj: str | None = None
    telefone: str | None = None
    logo_url: str | None = None
    slogan: str | None = None
    cor_primaria: str | None = None
    cor_secundaria: str | None = None


class ConsultorUpdateRequest(BaseModel):
    nome: str | None = None
    cnpj: str | None = None
    telefone: str | None = None
    logo_url: str | None = None
    slogan: str | None = None
    cor_primaria: str | None = None
    cor_secundaria: str | None = None
    ativo: bool | None = None


@router.get("/clientes", response_model=list[ClienteOut])
def listar_clientes(db: Session = Depends(get_db)):
    tenants  = db.query(Tenant).order_by(Tenant.nome).all()
    produtos = db.query(ProdutoSaas).order_by(ProdutoSaas.nome).all()
    consultores = {c.id: c.nome for c in db.query(Consultor).all()}
    entitlements = {
        (e.tenant_id, e.produto_saas_id): e.ativo
        for e in db.query(TenantProdutoSaas).all()
    }

    return [
        ClienteOut(
            tenant_id=t.id,
            nome=t.nome,
            cnpj=t.cnpj,
            ativo=t.ativo,
            consultor_id=t.consultor_id,
            consultor_nome=consultores.get(t.consultor_id),
            produtos=[
                ProdutoEntitlementOut(
                    produto_saas_id=p.id,
                    slug=p.slug,
                    nome=p.nome,
                    ativo=entitlements.get((t.id, p.id), False),
                )
                for p in produtos
            ],
        )
        for t in tenants
    ]


@router.post("/clientes", response_model=ClienteOut, status_code=201)
def criar_cliente(body: ClienteCreateRequest, db: Session = Depends(get_db)):
    if db.query(Tenant).filter(Tenant.cnpj == limpar_cnpj(body.cnpj)).first():
        raise HTTPException(status_code=400, detail="CNPJ já cadastrado")

    if body.consultor_id is not None:
        if not db.query(Consultor).filter(Consultor.id == body.consultor_id).first():
            raise HTTPException(status_code=404, detail="Consultor não encontrado")

    if body.usuario_login and db.query(Usuario).filter(Usuario.login == body.usuario_login.strip()).first():
        raise HTTPException(status_code=400, detail="Login já cadastrado")

    tenant = TenantService(db).criar(body.nome, body.cnpj, consultor_id=body.consultor_id)

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

    return ClienteOut(
        tenant_id=tenant.id, nome=tenant.nome, cnpj=tenant.cnpj, ativo=tenant.ativo,
        consultor_id=tenant.consultor_id, consultor_nome=None, produtos=[],
    )


@router.put("/clientes/{tenant_id}", response_model=ClienteOut)
def atualizar_cliente(tenant_id: int, body: ClienteUpdateRequest, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if body.nome is not None:
        tenant.nome = body.nome
    if body.cnpj is not None:
        tenant.cnpj = limpar_cnpj(body.cnpj)
    if body.ativo is not None:
        tenant.ativo = body.ativo
    if body.limpar_consultor:
        tenant.consultor_id = None
    elif body.consultor_id is not None:
        if not db.query(Consultor).filter(Consultor.id == body.consultor_id).first():
            raise HTTPException(status_code=404, detail="Consultor não encontrado")
        tenant.consultor_id = body.consultor_id
    db.commit()

    consultor_nome = None
    if tenant.consultor_id:
        consultor = db.query(Consultor).filter(Consultor.id == tenant.consultor_id).first()
        consultor_nome = consultor.nome if consultor else None

    return ClienteOut(
        tenant_id=tenant.id, nome=tenant.nome, cnpj=tenant.cnpj, ativo=tenant.ativo,
        consultor_id=tenant.consultor_id, consultor_nome=consultor_nome, produtos=[],
    )


@router.get("/produtos", response_model=list[ProdutoSaasOut])
def listar_produtos(db: Session = Depends(get_db)):
    return db.query(ProdutoSaas).order_by(ProdutoSaas.nome).all()


@router.put("/clientes/{tenant_id}/produtos/{produto_id}", response_model=ProdutoEntitlementOut)
def alternar_entitlement(
    tenant_id: int,
    produto_id: int,
    body: EntitlementRequest,
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    produto = db.query(ProdutoSaas).filter(ProdutoSaas.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    entitlement = (
        db.query(TenantProdutoSaas)
        .filter(TenantProdutoSaas.tenant_id == tenant_id, TenantProdutoSaas.produto_saas_id == produto_id)
        .first()
    )
    if not entitlement:
        entitlement = TenantProdutoSaas(tenant_id=tenant_id, produto_saas_id=produto_id)
        db.add(entitlement)

    entitlement.ativo = body.ativo
    if body.ativo:
        entitlement.ativado_em = datetime.utcnow()
    db.commit()

    return ProdutoEntitlementOut(
        produto_saas_id=produto.id,
        slug=produto.slug,
        nome=produto.nome,
        ativo=entitlement.ativo,
    )


@router.put("/usuarios/{usuario_id}/senha", status_code=204)
def resetar_senha(usuario_id: int, body: SenhaResetRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    usuario.senha_hash = hash_senha(body.nova_senha)
    db.commit()


def _consultor_out(consultor: Consultor, db: Session) -> ConsultorOut:
    total_clientes = db.query(Tenant).filter(Tenant.consultor_id == consultor.id).count()
    return ConsultorOut(
        id=consultor.id,
        nome=consultor.nome,
        cnpj=consultor.cnpj,
        telefone=consultor.telefone,
        logo_url=consultor.logo_url,
        slogan=consultor.slogan,
        cor_primaria=consultor.cor_primaria,
        cor_secundaria=consultor.cor_secundaria,
        ativo=consultor.ativo,
        total_clientes=total_clientes,
    )


@router.get("/consultores", response_model=list[ConsultorOut])
def listar_consultores(db: Session = Depends(get_db)):
    consultores = db.query(Consultor).order_by(Consultor.nome).all()
    return [_consultor_out(c, db) for c in consultores]


@router.post("/consultores", response_model=ConsultorOut, status_code=201)
def criar_consultor(body: ConsultorCreateRequest, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.login == body.usuario_login.strip()).first():
        raise HTTPException(status_code=400, detail="Login já cadastrado")

    consultor = Consultor(
        nome=body.nome,
        cnpj=limpar_cnpj(body.cnpj) if body.cnpj else None,
        telefone=body.telefone,
        logo_url=body.logo_url,
        slogan=body.slogan,
        cor_primaria=body.cor_primaria or "#1d4ed8",
        cor_secundaria=body.cor_secundaria or "#1e40af",
    )
    db.add(consultor)
    db.flush()

    usuario = Usuario(
        consultor_id=consultor.id,
        login=body.usuario_login.strip(),
        senha_hash=hash_senha(body.usuario_senha),
        nome=body.nome,
        role="consultor",
    )
    db.add(usuario)
    db.commit()
    db.refresh(consultor)

    return _consultor_out(consultor, db)


@router.put("/consultores/{consultor_id}", response_model=ConsultorOut)
def atualizar_consultor(consultor_id: int, body: ConsultorUpdateRequest, db: Session = Depends(get_db)):
    consultor = db.query(Consultor).filter(Consultor.id == consultor_id).first()
    if not consultor:
        raise HTTPException(status_code=404, detail="Consultor não encontrado")

    if body.nome is not None:
        consultor.nome = body.nome
    if body.cnpj is not None:
        consultor.cnpj = limpar_cnpj(body.cnpj)
    if body.telefone is not None:
        consultor.telefone = body.telefone
    if body.logo_url is not None:
        consultor.logo_url = body.logo_url
    if body.slogan is not None:
        consultor.slogan = body.slogan
    if body.cor_primaria is not None:
        consultor.cor_primaria = body.cor_primaria
    if body.cor_secundaria is not None:
        consultor.cor_secundaria = body.cor_secundaria
    if body.ativo is not None:
        consultor.ativo = body.ativo
    db.commit()

    return _consultor_out(consultor, db)


@router.delete("/consultores/{consultor_id}", status_code=204)
def desativar_consultor(consultor_id: int, db: Session = Depends(get_db)):
    consultor = db.query(Consultor).filter(Consultor.id == consultor_id).first()
    if not consultor:
        raise HTTPException(status_code=404, detail="Consultor não encontrado")
    consultor.ativo = False
    db.commit()
