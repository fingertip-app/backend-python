"""add_description_embedding_to_experiences

Revision ID: a33043f20b0a
Revises: a1b2c3d4e5f6
Create Date: 2026-06-25 18:10:58.048112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'a33043f20b0a'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # experiences 테이블에 description_embedding 컬럼 추가
    op.add_column('experiences', sa.Column('description_embedding', Vector(1536), nullable=True))

    # 벡터 검색 성능을 위한 인덱스 추가 (HNSW)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_experiences_description_embedding_hnsw
        ON experiences
        USING hnsw (description_embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_experiences_description_embedding_hnsw")
    op.drop_column('experiences', 'description_embedding')
