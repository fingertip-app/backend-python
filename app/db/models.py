from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    provider = Column(String(50), nullable=False)  # kakao, google, apple
    nickname = Column(String(100), nullable=False)
    profile_image_url = Column(Text)
    preferred_categories = Column(ARRAY(String))
    preferred_content_types = Column(ARRAY(String))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Artisan(Base):
    __tablename__ = "artisans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    heritage_category = Column(String(100), nullable=False)
    certification_number = Column(String(100), unique=True)
    bio = Column(Text)
    profile_image_url = Column(Text)
    intro_video_url = Column(Text)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    artisan_id = Column(BigInteger, ForeignKey("artisans.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    cultural_story = Column(Text)
    category = Column(String(100), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    max_participants = Column(Integer, nullable=False)
    difficulty = Column(String(20))  # easy, medium, hard
    supported_languages = Column(ARRAY(String))
    location_address = Column(Text)
    location_lat = Column(Numeric(10, 7))
    location_lng = Column(Numeric(10, 7))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ExperienceSchedule(Base):
    __tablename__ = "experience_schedules"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    experience_id = Column(BigInteger, ForeignKey("experiences.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    available_slots = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    experience_id = Column(BigInteger, ForeignKey("experiences.id"), nullable=False)
    schedule_id = Column(BigInteger, ForeignKey("experience_schedules.id"), nullable=False)
    participants = Column(Integer, nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected, confirmed, cancelled
    request_message = Column(Text)
    qr_code = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    booking_id = Column(BigInteger, ForeignKey("bookings.id"), nullable=False, unique=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    experience_id = Column(BigInteger, ForeignKey("experiences.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    content = Column(Text)
    new_learnings = Column(Text)
    image_urls = Column(ARRAY(String))
    sentiment_score = Column(Numeric(3, 2))
    keywords = Column(ARRAY(String))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CardNews(Base):
    __tablename__ = "card_news"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content_type = Column(String(50), nullable=False)  # k_drama, k_pop, k_anime, festival
    image_url = Column(Text)
    ai_explanation = Column(Text)
    category_tags = Column(ARRAY(String))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CardNewsExperience(Base):
    __tablename__ = "card_news_experiences"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    card_news_id = Column(BigInteger, ForeignKey("card_news.id"), nullable=False)
    experience_id = Column(BigInteger, ForeignKey("experiences.id"), nullable=False)
    similarity_score = Column(Numeric(4, 3))

    __table_args__ = (UniqueConstraint("card_news_id", "experience_id"),)


class Wishlist(Base):
    __tablename__ = "wishlists"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    experience_id = Column(BigInteger, ForeignKey("experiences.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "experience_id"),)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class HeritageItem(Base):
    __tablename__ = "heritage_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)  # 문화재청, 국가유산포털 등
    external_id = Column(String(100), unique=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    description = Column(Text)
    history = Column(Text)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)