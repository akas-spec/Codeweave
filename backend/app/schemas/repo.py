from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class RepoConnectRequest(BaseModel):
    github_url: str  # e.g. "https://github.com/owner/repo"

class RepoResponse(BaseModel):
    id: int
    name: str
    full_name: str
    github_url: str
    description: Optional[str] = None
    default_branch: str
    language: Optional[str] = None
    ingestion_status: str
    ingestion_progress: int
    total_chunks: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class RepoListResponse(BaseModel):
    repositories: list[RepoResponse]
    total: int

class IngestionStatusResponse(BaseModel):
    repository_id: int
    status: str
    progress: int
    total_chunks: int
    error: Optional[str] = None
