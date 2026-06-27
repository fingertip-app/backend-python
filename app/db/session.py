from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_size=2, max_overflow=2)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
