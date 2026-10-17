"""add metadata columns to vector_documents

Revision ID: a1b2c3d4e5f6
Revises: 2239b6f2be80
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2239b6f2be80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vector_documents', sa.Column('source', sa.String(length=100), nullable=True))
    op.add_column('vector_documents', sa.Column('title', sa.String(length=255), nullable=True))
    op.add_column('vector_documents', sa.Column('category', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('vector_documents', 'category')
    op.drop_column('vector_documents', 'title')
    op.drop_column('vector_documents', 'source')
