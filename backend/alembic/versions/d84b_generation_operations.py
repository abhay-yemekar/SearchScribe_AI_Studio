"""Durable generation idempotency and daily reservations."""

import sqlalchemy as sa

from alembic import op

revision = "d84b_generation_operations"
down_revision = "c73a_security_email_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result_version", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "request_key"),
    )
    op.create_index("ix_generation_operations_user_id", "generation_operations", ["user_id"])
    op.create_table(
        "generation_budgets",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_generation_budgets_expires_at", "generation_budgets", ["expires_at"])


def downgrade() -> None:
    op.drop_table("generation_budgets")
    op.drop_table("generation_operations")
