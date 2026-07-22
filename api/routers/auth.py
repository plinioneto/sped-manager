"""
POST /auth/token   → login (CNPJ para cliente, e-mail para admin) + senha
POST /auth/senha   → troca a própria senha (exige autenticação + senha atual)
GET  /auth/me      → dados do usuário autenticado (+ produtos SaaS ativos, se cliente)
"""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.models.usuario import Usuario
from app.models.tenant import Tenant
from app.models.consultor import Consultor
from app.models.produto_saas import ProdutoSaas
from app.models.tenant_produto_saas import TenantProdutoSaas
from api.auth import criar_token, hash_senha, verificar_senha
from api.deps import get_db, get_current_usuario

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: Optional[int] = None
    nome: str
    login: str


class SenhaRequest(BaseModel):
    senha_atual: str
    nova_senha: str


@router.post("/token", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    raw    = form.username.strip()
    digits = re.sub(r"\D", "", raw)
    lower  = raw.lower()

    usuario = (
        db.query(Usuario)
        .filter(Usuario.login.in_({digits, lower}), Usuario.ativo == True)
        .first()
    )

    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")

    if not verificar_senha(form.password, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Senha incorreta")

    if usuario.role == "cliente":
        tenant = db.query(Tenant).filter(Tenant.id == usuario.tenant_id).first()
        if not tenant or not tenant.ativo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cliente inativo")

    if usuario.role == "consultor":
        consultor = db.query(Consultor).filter(Consultor.id == usuario.consultor_id).first()
        if not consultor or not consultor.ativo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Consultor inativo")

    return TokenResponse(
        access_token=criar_token(usuario.id, usuario.role, usuario.tenant_id),
        role=usuario.role,
        tenant_id=usuario.tenant_id,
        nome=usuario.nome,
        login=usuario.login,
    )


@router.post("/senha", status_code=204)
def trocar_senha(
    body: SenhaRequest,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    if not verificar_senha(body.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Senha atual incorreta")
    usuario.senha_hash = hash_senha(body.nova_senha)
    db.commit()


@router.get("/me")
def me(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    out = {
        "usuario_id":   usuario.id,
        "nome":         usuario.nome,
        "login":        usuario.login,
        "role":         usuario.role,
        "tenant_id":    usuario.tenant_id,
        "consultor_id": usuario.consultor_id,
    }
    if usuario.role == "cliente":
        slugs = (
            db.query(ProdutoSaas.slug)
            .join(TenantProdutoSaas, TenantProdutoSaas.produto_saas_id == ProdutoSaas.id)
            .filter(
                TenantProdutoSaas.tenant_id == usuario.tenant_id,
                TenantProdutoSaas.ativo == True,
                ProdutoSaas.ativo == True,
            )
            .all()
        )
        out["produtos_ativos"] = [s[0] for s in slugs]
    return out
