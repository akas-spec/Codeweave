import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.repository import Repository, IngestionStatus
from app.models.user import User
from app.schemas.repo import (
    RepoConnectRequest,
    RepoResponse,
    RepoListResponse,
    IngestionStatusResponse,
)
from app.services.github_service import GitHubService
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)
router = APIRouter()


async def run_ingestion_background(
    repo_id: int,
    access_token: str | None,
    db_url: str,
):
    """Background task to run ingestion."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()
        if repo:
            # await GitHubService.clone_repository(repo.github_url, local_path)
            service = IngestionService(db)
            await service.ingest_repository(repo, access_token=access_token)

    await engine.dispose()


@router.post("/connect", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def connect_repository(
    request: RepoConnectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Connect a GitHub repository to CodeWeave."""
    # Parse GitHub URL
    try:
        owner, repo_name = GitHubService.parse_github_url(request.github_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    full_name = f"{owner}/{repo_name}"

    # Check if already connected
    existing = await db.execute(
        select(Repository).where(Repository.full_name == full_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Repository {full_name} is already connected")

    # Fetch repo info from GitHub
    github_service = GitHubService(access_token=current_user.github_access_token)
    try:
        repo_info = await github_service.get_repo_info(owner, repo_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch repo info: {e}")

    # Create repository record
    repository = Repository(
        name=repo_info.get("name", repo_name),
        full_name=full_name,
        github_url=request.github_url,
        description=repo_info.get("description"),
        default_branch=repo_info.get("default_branch", "main"),
        language=repo_info.get("language"),
        ingestion_status=IngestionStatus.PENDING,
        owner_id=current_user.id,
    )
    db.add(repository)
    await db.flush()
    await db.refresh(repository)

    logger.info(f"Connected repository: {full_name}")
    return repository


@router.post("/{repo_id}/ingest")
async def trigger_ingestion(
    repo_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger ingestion for a connected repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repository = result.scalar_one_or_none()

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repository.ingestion_status in (IngestionStatus.CLONING, IngestionStatus.PARSING, IngestionStatus.EMBEDDING):
        raise HTTPException(status_code=409, detail="Ingestion already in progress")

    # Reset status
    repository.ingestion_status = IngestionStatus.PENDING
    repository.ingestion_progress = 0
    repository.ingestion_error = None
    await db.commit()

    # Run ingestion in background
    from app.config import settings
    background_tasks.add_task(
        run_ingestion_background,
        repo_id=repository.id,
        access_token=current_user.github_access_token,
        db_url=settings.DATABASE_URL,
    )

    return {"message": "Ingestion started", "repository_id": repo_id}


@router.get("/{repo_id}/status", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get ingestion status for a repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repository = result.scalar_one_or_none()

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    return IngestionStatusResponse(
        repository_id=repository.id,
        status=repository.ingestion_status.value,
        progress=repository.ingestion_progress,
        total_chunks=repository.total_chunks,
        error=repository.ingestion_error,
    )


@router.get("/github")
async def list_github_repositories(
    current_user: User = Depends(get_current_user),
):
    """List GitHub repositories accessible to the authenticated user."""
    github_service = GitHubService(access_token=current_user.github_access_token)
    try:
        repos = await github_service.get_user_repos()
        return repos
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch GitHub repos: {e}")

@router.get("", response_model=RepoListResponse)
async def list_repositories(
    db: AsyncSession = Depends(get_db),
):
    """List all connected repositories."""
    result = await db.execute(select(Repository).order_by(Repository.created_at.desc()))
    repos = result.scalars().all()

    return RepoListResponse(
        repositories=[RepoResponse.model_validate(r) for r in repos],
        total=len(repos),
    )
