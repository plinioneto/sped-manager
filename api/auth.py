"""
Autenticação JWT.

Login: POST /auth/token  { cnpj, senha }
       → { access_token, token_type }

O token carrega { sub: str(tenant_id), cnpj }.
Trocar para email+senha no futuro é só mudar o campo de lookup aqui.
"""

import os
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY  = os.environ["JWT_SECRET"]          # obrigatório no .env
ALGORITHM   = "HS256"
TOKEN_TTL_H = int(os.getenv("JWT_TTL_HOURS", "24"))

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2  = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verificar_senha(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def hash_senha(plain: str) -> str:
    return pwd_ctx.hash(plain)


def criar_token(tenant_id: int, cnpj: str) -> str:
    payload = {
        "sub":  str(tenant_id),
        "cnpj": cnpj,
        "exp":  datetime.utcnow() + timedelta(hours=TOKEN_TTL_H),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
