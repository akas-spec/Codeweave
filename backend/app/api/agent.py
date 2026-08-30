import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.repository import Repository, IngestionStatus
from app.schemas.agent import AgentFixRequest, AgentFixResponse, AgentToolCall, AgentStatus
from app.services.github_service import GitHubService

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job store for MVP (use Redis for production)
_agent_jobs: dict[str, AgentFixResponse] = {}


async def _run_agent_background(
    repo_id: int,
    issue_description: str,
    file_path: str | None,
    job_id: str,
    db_url: str,
):
    """Background task that runs the agent."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import settings
    from app.services.agent import AgentOrchestrator

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            result = await db.execute(select(Repository).where(Repository.id == repo_id))
            repository = result.scalar_one_or_none()
            if not repository:
                _agent_jobs[job_id] = AgentFixResponse(
                    job_id=job_id,
                    status=AgentStatus.FAILED,
                    message="Repository not found",
                )
                return

            # Get repo clone path
            github_service = GitHubService()
            repo_path = github_service.get_clone_path(repository.full_name)
            if not repo_path.exists():
                # Re-clone if needed
                repo_path = github_service.clone_repo(repository.github_url, repository.full_name)

            # Run agent
            orchestrator = AgentOrchestrator(
                db=db,
                repository=repository,
                repo_path=repo_path,
                access_token=None,  # TODO: get from user
            )
            session = await orchestrator.run(issue_description, file_path)

            # Store result
            _agent_jobs[job_id] = AgentFixResponse(
                job_id=job_id,
                status=AgentStatus(session.status),
                message=session.summary,
                iterations=session.iterations,
                tool_calls=[
                    AgentToolCall(
                        tool=tc.tool,
                        input=tc.args,
                        output=tc.output[:500],
                        success=tc.success,
                    )
                    for tc in session.tool_calls
                ],
                pr_url=session.pr_url,
            )

    except Exception as e:
        logger.error("Agent background task failed: %s", e)
        _agent_jobs[job_id] = AgentFixResponse(
            job_id=job_id,
            status=AgentStatus.FAILED,
            message=f"Agent error: {e}",
        )
    finally:
        await engine.dispose()


@router.post("/fix", response_model=AgentFixResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_agent_fix(
    request: AgentFixRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an autonomous fix for an issue. Returns a job_id to poll for status."""
    # Validate repo
    result = await db.execute(
        select(Repository).where(Repository.id == request.repository_id)
    )
    repository = result.scalar_one_or_none()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repository.ingestion_status != IngestionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Repository not yet ingested")

    import uuid
    job_id = str(uuid.uuid4())[:8]

    # Initialize job as running
    _agent_jobs[job_id] = AgentFixResponse(
        job_id=job_id,
        status=AgentStatus.RUNNING,
        message="Agent is working on the fix...",
    )

    # Launch background task
    from app.config import settings
    background_tasks.add_task(
        _run_agent_background,
        repo_id=repository.id,
        issue_description=request.issue_description,
        file_path=request.file_path,
        job_id=job_id,
        db_url=settings.DATABASE_URL,
    )

    return _agent_jobs[job_id]


@router.get("/status/{job_id}", response_model=AgentFixResponse)
async def get_agent_status(job_id: str):
    """Poll the status of an agent fix job."""
    if job_id not in _agent_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _agent_jobs[job_id]


@router.get("/jobs")
async def list_agent_jobs():
    """List all agent jobs (recent first)."""
    return {
        "jobs": list(_agent_jobs.values()),
        "total": len(_agent_jobs),
    }
