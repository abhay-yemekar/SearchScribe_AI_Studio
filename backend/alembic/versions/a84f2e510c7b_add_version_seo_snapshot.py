"""add version SEO snapshot

Revision ID: a84f2e510c7b
Revises: 216ba5d8dc1c
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a84f2e510c7b"
down_revision: str | Sequence[str] | None = "216ba5d8dc1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("article_versions") as batch_op:
        batch_op.add_column(sa.Column("seo_snapshot", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("article_versions") as batch_op:
        batch_op.drop_column("seo_snapshot")
