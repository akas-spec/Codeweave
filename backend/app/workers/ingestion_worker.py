"""
Ingestion Worker

This worker can be run as a standalone process to handle repository ingestion.
Usage: python -m app.workers.ingestion_worker

For the MVP, we use FastAPI's BackgroundTasks. This worker is for scaling later.
"""
import asyncio
import logging
import json
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.config import settings
from app.models.repository import Repository
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

QUEUE_NAME = "codeweave:ingestion"


async def process_ingestion_job(job_data: dict):
    """Process a single ingestion job."""
    repo_id = job_data["repository_id"]
    access_token = job_data.get("access_token")

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        repository = result.scalar_one_or_none()

        if not repository:
            logger.error(f"Repository {repo_id} not found")
            return

        service = IngestionService(db)
        await service.ingest_repository(repository, access_token=access_token)

    await engine.dispose()


async def worker_loop():
    """Main worker loop: listen for ingestion jobs on Redis queue."""
    redis = aioredis.from_url(settings.REDIS_URL)
    logger.info(f"Ingestion worker started. Listening on queue: {QUEUE_NAME}")

    while True:
        try:
            # Block until a job is available (timeout 30s)
            result = await redis.brpop(QUEUE_NAME, timeout=30)
            if result:
                _, raw_data = result
                job_data = json.loads(raw_data)
                logger.info(f"Processing ingestion job: {job_data}")
                await process_ingestion_job(job_data)
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    asyncio.run(worker_loop())
