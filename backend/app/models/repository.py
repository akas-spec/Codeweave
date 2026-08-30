from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.database import Base

class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    full_name = Column(String(512), nullable=False, unique=True)  # e.g. "owner/repo"
    github_url = Column(String(1024), nullable=False)
    description = Column(String(2048), nullable=True)
    default_branch = Column(String(255), default="main")
    language = Column(String(100), nullable=True)
    ingestion_status = Column(SQLEnum(IngestionStatus), default=IngestionStatus.PENDING)
    ingestion_progress = Column(Integer, default=0)  # 0-100 percentage
    ingestion_error = Column(String(2048), nullable=True)
    total_chunks = Column(Integer, default=0)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    owner = relationship("User", back_populates="repositories")
    documents = relationship("Document", back_populates="repository", cascade="all, delete-orphan")
