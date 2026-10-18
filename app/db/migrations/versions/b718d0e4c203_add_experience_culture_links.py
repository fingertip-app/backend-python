"""Add AI-owned reviewed experience/culture links."""
from alembic import op
import sqlalchemy as sa

revision = "b718d0e4c203"
down_revision = "a33043f20b0a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experience_culture_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("experience_id", sa.BigInteger(), sa.ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("heritage_item_id", sa.BigInteger(), sa.ForeignKey("heritage_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("technique", sa.String(100), nullable=False),
        sa.Column("relation_kind", sa.String(30), nullable=False),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("evidence_excerpt", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_experience_culture_links_lookup", "experience_culture_links",
                    ["technique", "review_status", "experience_id"])


def downgrade():
    op.drop_index("ix_experience_culture_links_lookup", table_name="experience_culture_links")
    op.drop_table("experience_culture_links")
