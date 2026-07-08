"""
Rotas do módulo de administração — todas exigem Depends(get_admin).

GET /admin/clientes                              → lista de tenants + entitlement por produto
GET /admin/produtos                              → catálogo de produtos SaaS
PUT /admin/clientes/{tenant_id}/produtos/{produto_id} → ativa/desativa produto para o tenant
PUT /admin/usuarios/{usuario_id}/senha           → admin reseta senha de qualquer usuário
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.produto_saas import ProdutoSaas
from app.models.tenant_produto_saas import TenantProdutoSaas
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


@router.get("/clientes", response_model=list[ClienteOut])
def listar_clientes(db: Session = Depends(get_db)):
    tenants  = db.query(Tenant).order_by(Tenant.nome).all()
    produtos = db.query(ProdutoSaas).order_by(ProdutoSaas.nome).all()
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
