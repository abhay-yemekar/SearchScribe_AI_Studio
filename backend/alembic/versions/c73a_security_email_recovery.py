"""Persistent security email tokens, quotas and immediate session revocation."""

import sqlalchemy as sa

from alembic import op

revision = "c73a_security_email_recovery"
down_revision = "b91e_google_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(
            sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
        )
    # Existing Google identities were created only after nonce-bound Google
    # verification of this account's email, including explicit same-email linking.
    op.execute(
        sa.text(
            "UPDATE users SET email_verified = true WHERE id IN "
            "(SELECT user_id FROM provider_identities WHERE provider = 'google')"
        )
    )
    with op.batch_alter_table("refresh_tokens") as batch:
        batch.add_column(
            sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
        )
    op.create_table(
        "security_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_security_tokens_user_id", "security_tokens", ["user_id"])
    op.create_index("ix_security_tokens_token_hash", "security_tokens", ["token_hash"], unique=True)
    op.create_table(
        "security_rate_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_security_rate_buckets_expires_at", "security_rate_buckets", ["expires_at"])


def downgrade() -> None:
    op.drop_table("security_rate_buckets")
    op.drop_table("security_tokens")
    with op.batch_alter_table("refresh_tokens") as batch:
        batch.drop_column("session_version")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("session_version")
        batch.drop_column("email_verified")
