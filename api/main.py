"""
FastAPI — entry point.

Rodar localmente:
    uvicorn api.main:app --reload --port 8000

Documentação interativa:
    http://localhost:8000/docs
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, kpis, admin

app = FastAPI(
    title="SPED Manager API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# CORS — em produção, restringir para o domínio do frontend
_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(kpis.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
