"""model_review_v2 — operações sem custo de espaço

Inclui apenas operações que não reescrevem tabelas grandes:
  - ADD COLUMN nullable (fonte, cst_pis, cst_cofins, aliq_pis, aliq_cofins)
  - RENAME COLUMN chv_doc → chv_nfe em itens_fiscais e icms_c190
  - Text → JSONB em fabricantes.aliases e marcas.aliases (tabelas pequenas ~kB)
  - String → Numeric em icms_c190.aliq_icms (tabela ~122MB — reescrita necessária)
  - UniqueConstraints em documentos_fiscais e itens_fiscais

Operações Float → Numeric(15,2) nos campos vl_* ficaram na migration seguinte
(model_review_v2b) pois exigem reescrita de tabelas grandes (254MB + 122MB + 50MB)
e o banco não tem espaço suficiente agora.

Revision ID: 5a7e9db4919c
Revises: 8f8fc05b0864
Create Date: 2026-05-29 08:29:36.955258
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '5a7e9db4919c'
down_revision: Union[str, Sequence[str], None] = '8f8fc05b0864'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── documentos_fiscais ────────────────────────────────────────────────────
    # ADD COLUMN: instantâneo no PostgreSQL 11+ (sem reescrita)
    op.add_column('documentos_fiscais', sa.Column('fonte', sa.String(length=3), nullable=True))
    # UniqueConstraint: cria índice — usa algum espaço mas não reescreve a tabela
    op.create_unique_constraint('uq_documento_tenant_chave', 'documentos_fiscais', ['tenant_id', 'chv_nfe'])

    # ── fabricantes / marcas ──────────────────────────────────────────────────
    # Tabelas globais pequenas (~kB) — reescrita não é problema
    op.alter_column('fabricantes', 'aliases',
               existing_type=sa.TEXT(),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=True,
               postgresql_using='aliases::jsonb')
    op.alter_column('marcas', 'aliases',
               existing_type=sa.TEXT(),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=True,
               postgresql_using='aliases::jsonb')

    # ── icms_c190 ─────────────────────────────────────────────────────────────
    # aliq_icms: String → Numeric (era workaround para SQLite; reescreve 122MB)
    op.alter_column('icms_c190', 'aliq_icms',
               existing_type=sa.VARCHAR(length=10),
               type_=sa.Numeric(precision=7, scale=4),
               existing_nullable=True,
               postgresql_using='aliq_icms::numeric')
    # Rename: instantâneo
    op.alter_column('icms_c190', 'chv_doc', new_column_name='chv_nfe')

    # ── itens_fiscais ─────────────────────────────────────────────────────────
    # ADD COLUMNs nullable: instantâneos
    op.add_column('itens_fiscais', sa.Column('cst_pis', sa.String(length=3), nullable=True))
    op.add_column('itens_fiscais', sa.Column('cst_cofins', sa.String(length=3), nullable=True))
    op.add_column('itens_fiscais', sa.Column('aliq_pis', sa.Numeric(precision=7, scale=4), nullable=True))
    op.add_column('itens_fiscais', sa.Column('aliq_cofins', sa.Numeric(precision=7, scale=4), nullable=True))
    # Rename: instantâneo
    op.alter_column('itens_fiscais', 'chv_doc', new_column_name='chv_nfe')
    # UniqueConstraint
    op.create_unique_constraint('uq_item_tenant_chave', 'itens_fiscais', ['tenant_id', 'chv_nfe', 'num_item'])


def downgrade() -> None:
    op.drop_constraint('uq_item_tenant_chave', 'itens_fiscais', type_='unique')
    op.alter_column('itens_fiscais', 'chv_nfe', new_column_name='chv_doc')
    op.drop_column('itens_fiscais', 'aliq_cofins')
    op.drop_column('itens_fiscais', 'aliq_pis')
    op.drop_column('itens_fiscais', 'cst_cofins')
    op.drop_column('itens_fiscais', 'cst_pis')

    op.alter_column('icms_c190', 'chv_nfe', new_column_name='chv_doc')
    op.alter_column('icms_c190', 'aliq_icms',
               existing_type=sa.Numeric(precision=7, scale=4),
               type_=sa.VARCHAR(length=10),
               existing_nullable=True)

    op.alter_column('marcas', 'aliases',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.TEXT(),
               existing_nullable=True)
    op.alter_column('fabricantes', 'aliases',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.TEXT(),
               existing_nullable=True)

    op.drop_constraint('uq_documento_tenant_chave', 'documentos_fiscais', type_='unique')
    op.drop_column('documentos_fiscais', 'fonte')
