"""충북 공모전 전용 테이블. 기존 app/db/models.py 테이블과 분리되어 있어
기존 FastAPI 프로세스/코드는 이 테이블의 존재 자체를 알지 못한다."""

from datetime import datetime, timezone

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class ChungbukHeritageItem(Base):
    __tablename__ = "chungbuk_heritage_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)
    external_id = Column(String(100), unique=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    region = Column(String(50), nullable=False, default="충북")
    description = Column(Text)
    history = Column(Text)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    vector_documents = relationship(
        "ChungbukVectorDocument", back_populates="heritage_item", cascade="all, delete-orphan"
    )


class ChungbukVectorDocument(Base):
    __tablename__ = "chungbuk_vector_documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    heritage_item_id = Column(
        BigInteger, ForeignKey("chungbuk_heritage_items.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    source = Column(String(100), nullable=True)
    title = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    heritage_item = relationship("ChungbukHeritageItem", back_populates="vector_documents")

    __table_args__ = (
        Index("ix_chungbuk_vector_documents_heritage_item_id", "heritage_item_id"),
    )


class ChungbukArtisan(Base):
    """충북 시도무형유산 보유자(장인). 기존 artisans 테이블과 분리된 별도 테이블."""

    __tablename__ = "chungbuk_artisans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    heritage_category = Column(String(100), nullable=False)
    certification_number = Column(String(100), unique=True)
    is_chungbuk_certified = Column(Boolean, nullable=False, default=False)
    bio = Column(Text)
    profile_image_url = Column(Text)
    address = Column(Text)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class ChungbukCardNews(Base):
    """한물결 카드뉴스 충북 카테고리 전용 테이블."""

    __tablename__ = "chungbuk_card_news"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content_type = Column(String(50), nullable=False, default="chungbuk_local")
    image_url = Column(Text)
    ai_explanation = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
