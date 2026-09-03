from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    github_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    github_access_token = Column(String(512), nullable=True)  # Encrypted in production
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    repositories = relationship("Repository", back_populates="owner")
