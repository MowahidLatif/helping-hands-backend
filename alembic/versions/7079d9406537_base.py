"""base

Revision ID: 7079d9406537
Revises:
Create Date: 2025-08-20 20:15:24.809248

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "7079d9406537"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
