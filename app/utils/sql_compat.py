"""
Funções de data compatíveis com SQLite (dev) e PostgreSQL (prod).
Use estas funções em vez de func.strftime() nos repositórios.
"""
from sqlalchemy import func, cast, String
from app.utils.db import _is_sqlite


def sf_yearmonth(col):
    """Retorna string 'YYYYMM' — equivale a strftime('%Y%m', col)."""
    if _is_sqlite:
        return func.strftime("%Y%m", col)
    return func.to_char(col, "YYYYMM")


def sf_year(col):
    """Retorna string 'YYYY' — equivale a strftime('%Y', col)."""
    if _is_sqlite:
        return func.strftime("%Y", col)
    return func.to_char(col, "YYYY")


def sf_month(col):
    """Retorna string 'MM' — equivale a strftime('%m', col)."""
    if _is_sqlite:
        return func.strftime("%m", col)
    return func.to_char(col, "MM")


def sf_dow(col):
    """Dia da semana string: 0=Dom, 1=Seg … 6=Sáb (igual ao SQLite %w)."""
    if _is_sqlite:
        return func.strftime("%w", col)
    return cast(func.extract("dow", col), String)
