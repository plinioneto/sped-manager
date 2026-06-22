"""
Calcula e upserta gold_kpis_mensais a partir das tabelas silver.

Chamado pelo parser EFD e XML após cada importação.
Também pode ser rodado manualmente via scripts/recalcular_gold_kpis.py.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text


def calcular_kpis_mes(session: Session, tenant_id: int, ano: int, mes: int) -> dict:
    """Calcula KPIs de um mês e faz upsert em gold_kpis_mensais."""

    # Faturamento e ICMS das saídas (ind_oper=1)
    saidas = session.execute(text("""
        SELECT
            COALESCE(SUM(vl_doc), 0)      AS vl_faturamento,
            COUNT(*)                       AS qtd_notas,
            COALESCE(SUM(vl_icms), 0)     AS vl_icms_debito,
            COALESCE(SUM(vl_icms_st), 0)  AS vl_icms_st,
            COALESCE(SUM(vl_pis), 0)      AS vl_pis,
            COALESCE(SUM(vl_cofins), 0)   AS vl_cofins
        FROM notas_fiscais
        WHERE tenant_id = :tenant_id
          AND ind_oper = '1'
          AND EXTRACT(YEAR  FROM dt_doc) = :ano
          AND EXTRACT(MONTH FROM dt_doc) = :mes
    """), {"tenant_id": tenant_id, "ano": ano, "mes": mes}).fetchone()

    # Compras e ICMS das entradas (ind_oper=0)
    entradas = session.execute(text("""
        SELECT
            COALESCE(SUM(vl_doc), 0)   AS vl_compras,
            COUNT(*)                    AS qtd_notas,
            COALESCE(SUM(vl_icms), 0)  AS vl_icms_credito
        FROM notas_fiscais
        WHERE tenant_id = :tenant_id
          AND ind_oper = '0'
          AND EXTRACT(YEAR  FROM dt_doc) = :ano
          AND EXTRACT(MONTH FROM dt_doc) = :mes
    """), {"tenant_id": tenant_id, "ano": ano, "mes": mes}).fetchone()

    vl_faturamento  = saidas.vl_faturamento  or Decimal(0)
    qtd_notas_saida = saidas.qtd_notas       or 0
    vl_icms_debito  = saidas.vl_icms_debito  or Decimal(0)
    vl_icms_st      = saidas.vl_icms_st      or Decimal(0)
    vl_pis          = saidas.vl_pis          or Decimal(0)
    vl_cofins       = saidas.vl_cofins       or Decimal(0)

    vl_compras        = entradas.vl_compras     or Decimal(0)
    qtd_notas_entrada = entradas.qtd_notas      or 0
    vl_icms_credito   = entradas.vl_icms_credito or Decimal(0)

    ticket_medio  = (vl_faturamento / qtd_notas_saida) if qtd_notas_saida > 0 else Decimal(0)
    vl_icms_pagar = max(vl_icms_debito - vl_icms_credito, Decimal(0))

    session.execute(text("""
        INSERT INTO gold_kpis_mensais
            (tenant_id, ano, mes,
             vl_faturamento, qtd_notas_saida, ticket_medio,
             vl_compras, qtd_notas_entrada,
             vl_icms_debito, vl_icms_credito, vl_icms_pagar,
             vl_icms_st, vl_pis, vl_cofins, atualizado_em)
        VALUES
            (:tenant_id, :ano, :mes,
             :vl_faturamento, :qtd_notas_saida, :ticket_medio,
             :vl_compras, :qtd_notas_entrada,
             :vl_icms_debito, :vl_icms_credito, :vl_icms_pagar,
             :vl_icms_st, :vl_pis, :vl_cofins, :agora)
        ON CONFLICT (tenant_id, ano, mes) DO UPDATE SET
            vl_faturamento    = EXCLUDED.vl_faturamento,
            qtd_notas_saida   = EXCLUDED.qtd_notas_saida,
            ticket_medio      = EXCLUDED.ticket_medio,
            vl_compras        = EXCLUDED.vl_compras,
            qtd_notas_entrada = EXCLUDED.qtd_notas_entrada,
            vl_icms_debito    = EXCLUDED.vl_icms_debito,
            vl_icms_credito   = EXCLUDED.vl_icms_credito,
            vl_icms_pagar     = EXCLUDED.vl_icms_pagar,
            vl_icms_st        = EXCLUDED.vl_icms_st,
            vl_pis            = EXCLUDED.vl_pis,
            vl_cofins         = EXCLUDED.vl_cofins,
            atualizado_em     = EXCLUDED.atualizado_em
    """), {
        "tenant_id": tenant_id, "ano": ano, "mes": mes,
        "vl_faturamento": vl_faturamento, "qtd_notas_saida": qtd_notas_saida,
        "ticket_medio": ticket_medio, "vl_compras": vl_compras,
        "qtd_notas_entrada": qtd_notas_entrada, "vl_icms_debito": vl_icms_debito,
        "vl_icms_credito": vl_icms_credito, "vl_icms_pagar": vl_icms_pagar,
        "vl_icms_st": vl_icms_st, "vl_pis": vl_pis, "vl_cofins": vl_cofins,
        "agora": datetime.utcnow(),
    })
    session.commit()

    return {
        "ano": ano, "mes": mes,
        "vl_faturamento": float(vl_faturamento),
        "vl_compras": float(vl_compras),
        "vl_icms_pagar": float(vl_icms_pagar),
    }


def calcular_kpis_arquivo(session: Session, tenant_id: int, periodo_ini: str, periodo_fin: str) -> list[dict]:
    """
    Calcula KPIs para todos os meses cobertos por um arquivo importado.
    periodo_ini e periodo_fin no formato YYYYMMDD.
    """
    from datetime import date

    ini = date(int(periodo_ini[:4]), int(periodo_ini[4:6]), int(periodo_ini[6:]))
    fin = date(int(periodo_fin[:4]), int(periodo_fin[4:6]), int(periodo_fin[6:]))

    resultados = []
    ano, mes = ini.year, ini.month
    while (ano, mes) <= (fin.year, fin.month):
        r = calcular_kpis_mes(session, tenant_id, ano, mes)
        resultados.append(r)
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    return resultados
