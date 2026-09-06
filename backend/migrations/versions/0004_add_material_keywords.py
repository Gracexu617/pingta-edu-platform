"""add material keywords

Revision ID: 0004_add_material_keywords
Revises: 0003_create_collect_tasks
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_material_keywords"
down_revision: str | None = "0003_create_collect_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("keywords", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("materials", "keywords")
