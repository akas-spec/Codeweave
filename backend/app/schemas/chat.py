from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    question: str
    repository_id: int
    conversation_id: Optional[str] = None

class SourceChunk(BaseModel):
    source: str
    content: str
    relevance_score: float

class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk] = []
    conversation_id: str
    model_used: str
