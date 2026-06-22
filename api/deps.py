"""
Dependências reutilizáveis injetadas nas rotas via Depends().

get_db       → sessão SQLAlchemy (fecha no final do request)
get_tenant   → Tenant autenticado pelo JWT
"""

from typing import Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.utils.db import SessionLocal
from app.models.tenant import Tenant
from api.auth import decodificar_token, oauth2


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant(
    token: str = Depends(oauth2),
    db: Session = Depends(get_db),
) -> Tenant:
    payload   = decodificar_token(token)
    tenant_id = int(payload["sub"])
    tenant    = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.ativo == True).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Loja não encontrada")
    return tenant
