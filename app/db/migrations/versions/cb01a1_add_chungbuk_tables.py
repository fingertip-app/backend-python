"""add_chungbuk_tables

충북 공모전 전용 테이블 추가 (chungbuk_heritage_items, chungbuk_vector_documents,
chungbuk_artisans, chungbuk_card_news). 기존 테이블은 건드리지 않음 — 새 테이블만 CREATE.

Revision ID: cb01a1
Revises: a33043f20b0a
Create Date: 2026-06-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'cb01a1'
down_revision: Union[str, Sequence[str], None] = 'a33043f20b0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chungbuk_heritage_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('region', sa.String(length=50), nullable=False, server_default='충북'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('history', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    )

    op.create_table(
        'chungbuk_vector_documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('heritage_item_id', sa.BigInteger(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['heritage_item_id'], ['chungbuk_heritage_items.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_chungbuk_vector_documents_heritage_item_id',
        'chungbuk_vector_documents',
        ['heritage_item_id'],
    )
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chungbuk_vector_documents_embedding_hnsw
        ON chungbuk_vector_documents
        USING hnsw (embedding vector_cosine_ops)
    """)

    op.create_table(
        'chungbuk_artisans',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('heritage_category', sa.String(length=100), nullable=False),
        sa.Column('certification_number', sa.String(length=100), nullable=True),
        sa.Column('is_chungbuk_certified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('profile_image_url', sa.Text(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('certification_number'),
    )

    op.create_table(
        'chungbuk_card_news',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False, server_default='chungbuk_local'),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('ai_explanation', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('chungbuk_card_news')
    op.drop_table('chungbuk_artisans')
    op.execute("DROP INDEX IF EXISTS ix_chungbuk_vector_documents_embedding_hnsw")
    op.drop_index('ix_chungbuk_vector_documents_heritage_item_id', table_name='chungbuk_vector_documents')
    op.drop_table('chungbuk_vector_documents')
    op.drop_table('chungbuk_heritage_items')
