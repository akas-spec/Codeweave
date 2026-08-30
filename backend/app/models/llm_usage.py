from sqlalchemy import Column, BigInteger, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class LLMUsage(Base):
    """Tracks every LLM API call for cost accounting and monitoring."""
    __tablename__ = "llm_usage"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    model = Column(String(255), nullable=False)
    endpoint = Column(String(512), nullable=True)  # e.g. 'chat', 'agent_plan', 'agent_patch'
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 6), default=0.0)  # 0 for free tier
    latency_ms = Column(Integer, nullable=True)  # response time in milliseconds
    success = Column(Integer, default=1)  # 1=success, 0=error
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="llm_usage")
