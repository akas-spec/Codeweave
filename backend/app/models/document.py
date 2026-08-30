from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
from app.database import Base
from app.config import settings

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(1024), nullable=False)  # File path within repo
    content = Column(Text, nullable=False)  # The actual chunk text
    chunk_index = Column(Integer, default=0)  # Order within the file
    chunk_type = Column(String(50), nullable=True)  # 'function', 'class', 'markdown', 'text'
    language = Column(String(50), nullable=True)  # Programming language
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))  # 384-dim vector
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    repository = relationship("Repository", back_populates="documents")
