"""add persistent login lock state

Revision ID: 20260416_0003
Revises: 20260413_0002
Create Date: 2026-04-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260416_0003"
down_revision = "20260413_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("users", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("lock_reason", sa.String(length=64), nullable=True))
    op.alter_column("users", "failed_login_count", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "lock_reason")
    op.drop_column("users", "locked_at")
    op.drop_column("users", "failed_login_count")
