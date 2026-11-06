"""the fixture extension's own table — a second Alembic base beside the core's

Revision ID: ext_hello_0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "ext_hello_0001"
down_revision = None
branch_labels = ("ext_hello",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ext_hello",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("word", sa.String(40), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ext_hello")
