import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("Starting CodeWeave backend...")

    # 1. Initialise database (pgvector extension + tables)
    try:
        await init_db()
        logger.info("Database initialised")

        # 1b. Ensure a seed dev user exists (owner_id=1 is hardcoded in repos.py)
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.user import User
        async with AsyncSessionLocal() as session:
            existing = await session.execute(select(User).where(User.id == 1))
            if not existing.scalar_one_or_none():
                session.add(User(id=1, github_id=0, username="dev-user", email="dev@codeweave.local"))
                await session.commit()
                logger.info("Seed dev user created (id=1)")

    except Exception as e:
        logger.error("Database init failed: %s", e)

    # 2. Pre-load embedding model (slow first load, fast thereafter)
    try:
        from app.services.embeddings import EmbeddingService
        EmbeddingService.get_instance()
        logger.info("Embedding model loaded")
    except Exception as e:
        logger.warning("Embedding model load failed (non-fatal): %s", e)

    # 3. Initialise Redis cache (DB=0, LRU)
    try:
        from app.services.cache import init_cache
        init_cache(settings.REDIS_URL)
        logger.info("Redis cache initialised")
    except Exception as e:
        logger.warning("Redis cache init failed (non-fatal, caching disabled): %s", e)

    # 4. Initialise rate limiter
    try:
        from app.services.rate_limiter import init_rate_limiter
        init_rate_limiter(settings.REDIS_URL)
        logger.info("Rate limiter initialised")
    except Exception as e:
        logger.warning("Rate limiter init failed (non-fatal, rate limiting disabled): %s", e)

    logger.info("CodeWeave backend ready")
    yield

    # Shutdown
    logger.info("Shutting down CodeWeave backend...")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Autonomous Code Engineering Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
from app.api import auth, repos  # noqa: E402
from app.api import chat          # noqa: E402
from app.api import agent         # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(repos.router, prefix="/api/repos", tags=["Repositories"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    from app.services.cache import get_cache
    from app.services.embeddings import EmbeddingService

    redis_ok = False
    try:
        cache = get_cache()
        redis_ok = await cache.ping()
    except Exception:
        pass

    embed_ok = False
    try:
        EmbeddingService.get_instance()
        embed_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "services": {
            "redis": "ok" if redis_ok else "unavailable",
            "embeddings": "ok" if embed_ok else "unavailable",
            "llm": "configured" if settings.OPENROUTER_API_KEY else "not configured",
        },
    }
