"""model_review_v2b — Float → Numeric em campos vl_*

Converte todos os campos de valor monetário de DOUBLE_PRECISION para
Numeric(15,2), eliminando erros de representação binária (ex: 0.1+0.2=0.30000000000000004).

ATENÇÃO: esta migration reescreve três tabelas grandes:
  - documentos_fiscais (~50 MB)
  - icms_c190 (~122 MB)
  - itens_fiscais (~254 MB)

Requer ~430 MB de espaço livre temporário no banco.
Aplicar somente quando o Supabase tiver espaço suficiente (upgrade para Pro ou
após limpeza de dados antigos).

Revision ID: b3f1c2d4e5a6
Revises: 5a7e9db4919c
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b3f1c2d4e5a6'
down_revision: Union[str, Sequence[str], None] = '5a7e9db4919c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Campos vl_* por tabela
_DOCS_COLS = [
    'vl_doc', 'vl_desc', 'vl_merc', 'vl_bc_icms', 'vl_icms',
    'vl_bc_icms_st', 'vl_icms_st', 'vl_pis', 'vl_cofins',
]
_C190_COLS = [
    'vl_opr', 'vl_bc_icms', 'vl_icms', 'vl_bc_icms_st', 'vl_icms_st',
    'vl_red_bc', 'vl_pis', 'vl_cofins',
]
_ITEM_COLS = [
    'vl_item', 'vl_desc', 'vl_bc_icms', 'vl_icms', 'vl_pis', 'vl_cofins',
]


def upgrade() -> None:
    for col in _DOCS_COLS:
        op.alter_column('documentos_fiscais', col,
                   existing_type=sa.DOUBLE_PRECISION(precision=53),
                   type_=sa.Numeric(precision=15, scale=2),
                   existing_nullable=True)

    for col in _C190_COLS:
        op.alter_column('icms_c190', col,
                   existing_type=sa.DOUBLE_PRECISION(precision=53),
                   type_=sa.Numeric(precision=15, scale=2),
                   existing_nullable=True)

    # itens_fiscais: vl_* + qtd + aliq_icms
    for col in _ITEM_COLS:
        op.alter_column('itens_fiscais', col,
                   existing_type=sa.DOUBLE_PRECISION(precision=53),
                   type_=sa.Numeric(precision=15, scale=2),
                   existing_nullable=True)
    op.alter_column('itens_fiscais', 'qtd',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               type_=sa.Numeric(precision=15, scale=4),
               existing_nullable=True)
    op.alter_column('itens_fiscais', 'aliq_icms',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               type_=sa.Numeric(precision=7, scale=4),
               existing_nullable=True)


def downgrade() -> None:
    for col in reversed(_DOCS_COLS):
        op.alter_column('documentos_fiscais', col,
                   existing_type=sa.Numeric(precision=15, scale=2),
                   type_=sa.DOUBLE_PRECISION(precision=53),
                   existing_nullable=True)

    for col in reversed(_C190_COLS):
        op.alter_column('icms_c190', col,
                   existing_type=sa.Numeric(precision=15, scale=2),
                   type_=sa.DOUBLE_PRECISION(precision=53),
                   existing_nullable=True)

    for col in reversed(_ITEM_COLS):
        op.alter_column('itens_fiscais', col,
                   existing_type=sa.Numeric(precision=15, scale=2),
                   type_=sa.DOUBLE_PRECISION(precision=53),
                   existing_nullable=True)
    op.alter_column('itens_fiscais', 'qtd',
               existing_type=sa.Numeric(precision=15, scale=4),
               type_=sa.DOUBLE_PRECISION(precision=53),
               existing_nullable=True)
    op.alter_column('itens_fiscais', 'aliq_icms',
               existing_type=sa.Numeric(precision=7, scale=4),
               type_=sa.DOUBLE_PRECISION(precision=53),
               existing_nullable=True)
