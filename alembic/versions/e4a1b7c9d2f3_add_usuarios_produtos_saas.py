"""add_usuarios_produtos_saas

Revision ID: e4a1b7c9d2f3
Revises: a04f951ab3d1
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a1b7c9d2f3'
down_revision: Union[str, Sequence[str], None] = 'a04f951ab3d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=True),
    sa.Column('login', sa.String(), nullable=False),
    sa.Column('senha_hash', sa.String(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['lojas.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('login')
    )
    op.create_index(op.f('ix_usuarios_id'), 'usuarios', ['id'], unique=False)
    op.create_index(op.f('ix_usuarios_login'), 'usuarios', ['login'], unique=True)

    op.create_table('produtos_saas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=60), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('descricao', sa.String(), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_produtos_saas_id'), 'produtos_saas', ['id'], unique=False)

    op.create_table('tenant_produtos_saas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('produto_saas_id', sa.Integer(), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.Column('ativado_em', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['lojas.id'], ),
    sa.ForeignKeyConstraint(['produto_saas_id'], ['produtos_saas.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'produto_saas_id', name='uq_tenant_produto_saas')
    )
    op.create_index(op.f('ix_tenant_produtos_saas_id'), 'tenant_produtos_saas', ['id'], unique=False)
    op.create_index(op.f('ix_tenant_produtos_saas_tenant_id'), 'tenant_produtos_saas', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tenant_produtos_saas_tenant_id'), table_name='tenant_produtos_saas')
    op.drop_index(op.f('ix_tenant_produtos_saas_id'), table_name='tenant_produtos_saas')
    op.drop_table('tenant_produtos_saas')

    op.drop_index(op.f('ix_produtos_saas_id'), table_name='produtos_saas')
    op.drop_table('produtos_saas')

    op.drop_index(op.f('ix_usuarios_login'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_id'), table_name='usuarios')
    op.drop_table('usuarios')
