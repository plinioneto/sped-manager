"""
Autenticação JWT.

Login: POST /auth/token  { username, password }
       → { access_token, token_type, role, tenant_id }

O token carrega { sub: str(usuario_id), role, tenant_id }.
"""

import os
from datetime import datetime, timedelta

import bcrypt
import jwt
from jwt import PyJWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY  = os.environ["JWT_SECRET"]          # obrigatório no .env
ALGORITHM   = "HS256"
TOKEN_TTL_H = int(os.getenv("JWT_TTL_HOURS", "24"))

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verificar_senha(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_senha(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def criar_token(usuario_id: int, role: str, tenant_id: int | None) -> str:
    payload = {
        "sub":       str(usuario_id),
        "role":      role,
        "tenant_id": tenant_id,
        "exp":       datetime.utcnow() + timedelta(hours=TOKEN_TTL_H),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
