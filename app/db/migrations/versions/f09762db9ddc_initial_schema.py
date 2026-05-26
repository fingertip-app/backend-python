"""create AI heritage vector store

Revision ID: f09762db9ddc
Revises:
Create Date: 2026-05-22 21:19:20.370634

This baseline was narrowed before AI database deployment. Development databases
that applied an earlier version of this revision must be recreated.
"""

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f09762db9ddc"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "heritage_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("history", sa.Text(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(
        "ix_heritage_items_embedding_hnsw",
        "heritage_items",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_heritage_items_embedding_hnsw", table_name="heritage_items")
    op.drop_table("heritage_items")
