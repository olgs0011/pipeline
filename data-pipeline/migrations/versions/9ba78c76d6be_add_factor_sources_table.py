"""add factor_sources table

Revision ID: 9ba78c76d6be
Revises: c609c60be127
Create Date: 2026-10-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9ba78c76d6be"
down_revision: Union[str, Sequence[str], None] = "c609c60be127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "factor_sources",
        sa.Column("factor_code", sa.String(16), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=True),
        sa.Column("filter_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("match_method", sa.String(32), nullable=False, server_default="auto"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["factor_code"], ["factors.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("factor_code", "source_id"),
    )
    op.create_index("ix_factor_sources_external_id", "factor_sources", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_factor_sources_external_id", table_name="factor_sources")
    op.drop_table("factor_sources")