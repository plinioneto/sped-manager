"""
Funções de data compatíveis com SQLite (dev) e PostgreSQL (prod).
Use estas funções em vez de func.strftime() nos repositórios.

A verificação é feita em tempo de execução (não em import-time) para
garantir que o DATABASE_URL já esteja resolvido via st.secrets.
"""
import os
from sqlalchemy import func, cast, String


def _sqlite() -> bool:
    return "sqlite" in os.environ.get("DATABASE_URL", "sqlite")


def sf_yearmonth(col):
    """Retorna string 'YYYYMM' — equivale a strftime('%Y%m', col)."""
    if _sqlite():
        return func.strftime("%Y%m", col)
    return func.to_char(col, "YYYYMM")


def sf_year(col):
    """Retorna string 'YYYY' — equivale a strftime('%Y', col)."""
    if _sqlite():
        return func.strftime("%Y", col)
    return func.to_char(col, "YYYY")


def sf_month(col):
    """Retorna string 'MM' — equivale a strftime('%m', col)."""
    if _sqlite():
        return func.strftime("%m", col)
    return func.to_char(col, "MM")


def sf_dow(col):
    """Dia da semana string: 0=Dom, 1=Seg … 6=Sáb (igual ao SQLite %w)."""
    if _sqlite():
        return func.strftime("%w", col)
    return cast(func.extract("dow", col), String)
