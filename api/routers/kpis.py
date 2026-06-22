"""
GET /kpis/mensais          → todos os meses do tenant
GET /kpis/mensais/{ano}/{mes} → mês específico
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from decimal import Decimal

from app.models.gold_kpis_mensais import GoldKpisMensais
from app.models.tenant import Tenant
from api.deps import get_db, get_tenant

router = APIRouter(prefix="/kpis", tags=["kpis"])


class KpisMensaisOut(BaseModel):
    ano: int
    mes: int
    vl_faturamento: Decimal
    qtd_notas_saida: int
    ticket_medio: Decimal
    vl_compras: Decimal
    qtd_notas_entrada: int
    vl_icms_debito: Decimal
    vl_icms_credito: Decimal
    vl_icms_pagar: Decimal
    vl_icms_st: Decimal
    vl_pis: Decimal
    vl_cofins: Decimal

    class Config:
        from_attributes = True


@router.get("/mensais", response_model=list[KpisMensaisOut])
def listar_kpis_mensais(
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(GoldKpisMensais)
        .filter(GoldKpisMensais.tenant_id == tenant.id)
        .order_by(GoldKpisMensais.ano, GoldKpisMensais.mes)
        .all()
    )
    return rows


@router.get("/mensais/{ano}/{mes}", response_model=KpisMensaisOut)
def kpis_mes(
    ano: int,
    mes: int,
    tenant: Tenant = Depends(get_tenant),
    db: Session = Depends(get_db),
):
    row = (
        db.query(GoldKpisMensais)
        .filter(
            GoldKpisMensais.tenant_id == tenant.id,
            GoldKpisMensais.ano == ano,
            GoldKpisMensais.mes == mes,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Sem dados para {ano}/{mes:02d}")
    return row
