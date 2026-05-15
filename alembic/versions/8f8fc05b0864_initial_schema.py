"""initial_schema

Revision ID: 8f8fc05b0864
Revises: 
Create Date: 2026-05-13 20:22:37.535930

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f8fc05b0864'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import app.models  # noqa: F401 — registra todos os models
    from app.models.base import Base
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    import app.models  # noqa: F401
    from app.models.base import Base
    Base.metadata.drop_all(bind=op.get_bind())
