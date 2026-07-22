"""add_consultores

Revision ID: bd39c7157f46
Revises: e4a1b7c9d2f3
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd39c7157f46'
down_revision: Union[str, Sequence[str], None] = 'e4a1b7c9d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('consultores',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('cnpj', sa.String(length=14), nullable=True),
    sa.Column('telefone', sa.String(), nullable=True),
    sa.Column('logo_url', sa.String(), nullable=True),
    sa.Column('slogan', sa.String(), nullable=True),
    sa.Column('cor_primaria', sa.String(length=7), nullable=True),
    sa.Column('cor_secundaria', sa.String(length=7), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consultores_id'), 'consultores', ['id'], unique=False)

    op.add_column('lojas', sa.Column('consultor_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_lojas_consultor_id'), 'lojas', ['consultor_id'], unique=False)
    op.create_foreign_key('fk_lojas_consultor_id', 'lojas', 'consultores', ['consultor_id'], ['id'])

    op.add_column('usuarios', sa.Column('consultor_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_usuarios_consultor_id'), 'usuarios', ['consultor_id'], unique=False)
    op.create_foreign_key('fk_usuarios_consultor_id', 'usuarios', 'consultores', ['consultor_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_usuarios_consultor_id', 'usuarios', type_='foreignkey')
    op.drop_index(op.f('ix_usuarios_consultor_id'), table_name='usuarios')
    op.drop_column('usuarios', 'consultor_id')

    op.drop_constraint('fk_lojas_consultor_id', 'lojas', type_='foreignkey')
    op.drop_index(op.f('ix_lojas_consultor_id'), table_name='lojas')
    op.drop_column('lojas', 'consultor_id')

    op.drop_index(op.f('ix_consultores_id'), table_name='consultores')
    op.drop_table('consultores')
