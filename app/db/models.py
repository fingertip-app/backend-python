from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.db.base import Base


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
