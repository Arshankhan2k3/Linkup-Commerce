"""remove store_id from customer addresses

Revision ID: 0607e3b2c72c
Revises: e8d9f102b345
Create Date: 2026-09-16 11:29:22.836850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0607e3b2c72c'
down_revision: Union[str, Sequence[str], None] = 'e8d9f102b345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
