"""Baseline: messages and settings.

Revision ID: 0001
Revises:
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("repeat", sa.String(8), nullable=False, server_default="none"),
        sa.Column("repeat_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repeat_start", sa.String(5)),
        sa.Column("repeat_end", sa.String(5)),
        sa.Column("source", sa.String(8), nullable=False, server_default="api"),
        sa.Column("created_by", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_messages_enabled", "messages", ["enabled"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_messages_enabled", table_name="messages")
    op.drop_table("messages")
