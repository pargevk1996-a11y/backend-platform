"""user login and password-reset hard lock flags

Revision ID: 20260421_0003
Revises: 20260413_0002
Create Date: 2026-04-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260421_0003"
down_revision = "20260413_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("login_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column(
            "password_reset_blocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("users", "login_blocked", server_default=None)
    op.alter_column("users", "password_reset_blocked", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "password_reset_blocked")
    op.drop_column("users", "login_blocked")
