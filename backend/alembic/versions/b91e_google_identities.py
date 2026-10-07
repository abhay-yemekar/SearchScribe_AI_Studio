"""Google identities; passwordless users keep the existing session system."""

import sqlalchemy as sa

from alembic import op

revision = "b91e_google_identities"
down_revision = "a84f2e510c7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(255), nullable=True)
    op.create_table(
        "provider_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.UniqueConstraint("provider", "subject", name="uq_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )
    op.create_index("ix_provider_identities_user_id", "provider_identities", ["user_id"])


def downgrade() -> None:
    # Never invent passwords or drop passwordless accounts to make rollback fit.
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE password_hash IS NULL")
    ).scalar():
        raise RuntimeError(
            "Cannot downgrade while passwordless accounts exist; restore a backup instead"
        )
    op.drop_table("provider_identities")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(255), nullable=False)
