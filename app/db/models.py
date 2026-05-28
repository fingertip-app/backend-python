from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.db.base import Base

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship



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


class EmbeddingMetadata(Base):
    __tablename__ = "embedding_metadata"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    target_table = Column(String(100), nullable=False)   # "heritage_items" or "vector_documents"
    target_id = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending / done / failed
    error_message = Column(Text)
    embedded_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)