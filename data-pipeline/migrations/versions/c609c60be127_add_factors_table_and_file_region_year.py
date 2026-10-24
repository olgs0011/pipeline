"""add factors table and file region year

Revision ID: <ваш_id>
Revises: 3fa7f11c57ed
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c609c60be127"
down_revision: Union[str, Sequence[str], None] = "3fa7f11c57ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "factors",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("source_hint", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )

    op.add_column("files", sa.Column("region", sa.String(length=128), nullable=True))
    op.add_column("files", sa.Column("year", sa.Integer(), nullable=True))
    op.create_index("ix_files_dataset_year", "files", ["dataset_id", "year"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_files_dataset_year", table_name="files")
    op.drop_column("files", "year")
    op.drop_column("files", "region")
    op.drop_table("factors")