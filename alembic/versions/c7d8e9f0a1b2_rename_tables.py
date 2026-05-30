"""rename_tables — padronização de nomes de tabelas

Renomeações aplicadas:
  tenants             → lojas
  participantes       → fornecedores
  documentos_fiscais  → notas_fiscais
  itens_fiscais       → itens_nota_fiscal
  icms_c190           → resumo_fiscal
  departamentos       → departamentos_produto
  grupos              → grupos_produto
  categorias          → categorias_produto

Revision ID: c7d8e9f0a1b2
Revises: b3f1c2d4e5a6
Create Date: 2026-05-29
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'b3f1c2d4e5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAMES = [
    ("tenants",            "lojas"),
    ("participantes",      "fornecedores"),
    ("documentos_fiscais", "notas_fiscais"),
    ("itens_fiscais",      "itens_nota_fiscal"),
    ("icms_c190",          "resumo_fiscal"),
    ("departamentos",      "departamentos_produto"),
    ("grupos",             "grupos_produto"),
    ("categorias",         "categorias_produto"),
]


def upgrade() -> None:
    for old, new in RENAMES:
        op.rename_table(old, new)


def downgrade() -> None:
    for old, new in reversed(RENAMES):
        op.rename_table(new, old)
