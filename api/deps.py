"""
Dependências reutilizáveis injetadas nas rotas via Depends().

get_db               → sessão SQLAlchemy (fecha no final do request)
get_current_usuario  → Usuario autenticado pelo JWT
get_admin            → Usuario autenticado, exige role='admin'
get_tenant           → Tenant do Usuario autenticado, exige role='cliente'
"""

from typing import Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.utils.db import SessionLocal
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from api.auth import decodificar_token, oauth2


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_usuario(
    token: str = Depends(oauth2),
    db: Session = Depends(get_db),
) -> Usuario:
    payload    = decodificar_token(token)
    usuario_id = int(payload["sub"])
    usuario    = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado ou inativo")

    if usuario.role == "cliente":
        tenant = db.query(Tenant).filter(Tenant.id == usuario.tenant_id).first()
        if not tenant or not tenant.ativo:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cliente inativo")

    return usuario


def get_admin(usuario: Usuario = Depends(get_current_usuario)) -> Usuario:
    if usuario.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return usuario


def get_tenant(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> Tenant:
    if usuario.role != "cliente" or usuario.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a clientes")
    tenant = db.query(Tenant).filter(Tenant.id == usuario.tenant_id, Tenant.ativo == True).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Loja não encontrada")
    return tenant
