"""Guest posts: a queue a phone fills through the guest link, and the message a post becomes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nick", sa.String(16), nullable=False, server_default=""),
        sa.Column("text", sa.String(120), nullable=False, server_default=""),
        sa.Column("image", sa.String(40), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default="pending"),
        sa.Column("ip_hash", sa.String(16), nullable=False, server_default=""),
    )
    op.create_index("ix_posts_created_at", "posts", ["created_at"])
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("post_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("post_id")
    op.drop_index("ix_posts_created_at", table_name="posts")
    op.drop_table("posts")
