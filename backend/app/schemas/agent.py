from pydantic import BaseModel
from typing import Optional
from enum import Enum


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_ITERATIONS = "max_iterations_reached"


class AgentFixRequest(BaseModel):
    repository_id: int
    issue_description: str
    file_path: Optional[str] = None  # Optional hint: which file has the issue


class AgentToolCall(BaseModel):
    tool: str
    input: dict
    output: Optional[str] = None
    success: bool = True


class AgentFixResponse(BaseModel):
    job_id: str
    status: AgentStatus
    message: str
    iterations: int = 0
    tool_calls: list[AgentToolCall] = []
    patch: Optional[str] = None       # Unified diff of changes
    pr_url: Optional[str] = None      # GitHub PR URL if created
    test_output: Optional[str] = None
