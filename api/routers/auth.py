"""
POST /auth/token   → login por CNPJ + senha
POST /auth/senha   → define/troca senha (primeira vez ou reset)
GET  /auth/me      → dados do tenant autenticado
"""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from api.auth import criar_token, hash_senha, verificar_senha
from api.deps import get_db, get_tenant

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: int
    nome: str
    cnpj: str


class SenhaRequest(BaseModel):
    cnpj: str
    nova_senha: str


@router.post("/token", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    cnpj   = re.sub(r"\D", "", form.username)
    tenant = db.query(Tenant).filter(Tenant.cnpj == cnpj, Tenant.ativo == True).first()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="CNPJ não cadastrado")

    if not tenant.senha_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Senha não configurada — use POST /auth/senha para definir",
        )

    if not verificar_senha(form.password, tenant.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Senha incorreta")

    return TokenResponse(
        access_token=criar_token(tenant.id, tenant.cnpj),
        tenant_id=tenant.id,
        nome=tenant.nome,
        cnpj=tenant.cnpj,
    )


@router.post("/senha", status_code=204)
def definir_senha(body: SenhaRequest, db: Session = Depends(get_db)):
    """Define senha pela primeira vez. Em produção, proteger com código de convite."""
    cnpj   = re.sub(r"\D", "", body.cnpj)
    tenant = db.query(Tenant).filter(Tenant.cnpj == cnpj).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="CNPJ não cadastrado")
    tenant.senha_hash = hash_senha(body.nova_senha)
    db.commit()


@router.get("/me")
def me(tenant: Tenant = Depends(get_tenant)):
    return {
        "tenant_id": tenant.id,
        "nome":      tenant.nome,
        "cnpj":      tenant.cnpj,
        "grupo_id":  tenant.grupo_id,
    }
