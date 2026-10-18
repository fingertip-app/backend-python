from datetime import datetime
from enum import Enum as PyEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class EmbeddingStatus(str, PyEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class HeritageItem(Base):
    __tablename__ = "heritage_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)
    external_id = Column(String(100), unique=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    description = Column(Text)
    history = Column(Text)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    vector_documents = relationship("VectorDocument", back_populates="heritage_item", cascade="all, delete-orphan")


class VectorDocument(Base):
    __tablename__ = "vector_documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    heritage_item_id = Column(BigInteger, ForeignKey("heritage_items.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    heritage_item = relationship("HeritageItem", back_populates="vector_documents")

    __table_args__ = (
        Index('ix_vector_documents_heritage_item_id', 'heritage_item_id'),
    )
    
    source = Column(String(100), nullable=True)
    title = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)


class EmbeddingMetadata(Base):
    __tablename__ = "embedding_metadata"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    target_table = Column(String(100), nullable=False)
    target_id = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default=EmbeddingStatus.PENDING.value)
    error_message = Column(Text)
    embedded_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Experience(Base):
    """체험 프로그램 모델 (Spring Boot Experience 엔티티와 동기화)"""
    __tablename__ = "experiences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    cultural_story = Column(Text)
    category = Column(String(100), nullable=False)
    price = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    max_participants = Column(Integer, nullable=False)
    difficulty = Column(String(20))
    location_address = Column(Text)
    location_lat = Column(String(20))
    location_lng = Column(String(20))
    is_active = Column(Boolean, nullable=False, default=True)

    # AI 추천용 벡터 임베딩
    description_embedding = Column(Vector(1536))

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_experiences_is_active', 'is_active'),
        Index('ix_experiences_category', 'category'),
    )


class ExperienceCultureLink(Base):
    """AI-owned reviewed links; Spring owns the referenced experiences."""
    __tablename__ = "experience_culture_links"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    experience_id = Column(BigInteger, ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False)
    heritage_item_id = Column(BigInteger, ForeignKey("heritage_items.id", ondelete="CASCADE"), nullable=False)
    technique = Column(String(100), nullable=False)
    relation_kind = Column(String(30), nullable=False)
    evidence_url = Column(Text, nullable=False)
    evidence_excerpt = Column(Text, nullable=False)
    review_status = Column(String(20), nullable=False, default="pending")
    checked_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_experience_culture_links_lookup", "technique", "review_status", "experience_id"),
    )
