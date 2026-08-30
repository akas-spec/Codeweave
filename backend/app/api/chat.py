import json
import logging
import asyncio
from typing import AsyncIterator, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.repository import Repository, IngestionStatus
from app.schemas.chat import ChatRequest, ChatResponse, SourceChunk
from app.services.llm.base import ChatMessage, get_llm_provider
from app.services.retrieval import RetrievalService
from app.services.cost_tracker import CostTracker, TimedLLMCall
from app.services.cache import get_cache
from app.services.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)
router = APIRouter()

SYSTEM_PROMPT = """You are CodeWeave, an expert AI assistant specializing in software engineering.
You have been given relevant code and documentation from a repository as context.
Answer the user's question based ONLY on the provided context — do not hallucinate code or APIs that are not present.
If you cannot answer from the context, say so clearly.
When referencing code, cite the source file path."""


async def _stream_llm_response(
    messages: list[ChatMessage],
    model: str,
) -> AsyncIterator[str]:
    """Stream LLM response chunks as SSE data events."""
    import httpx
    from app.config import settings

    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": True,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream(
            "POST",
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://codeweave.dev",
                "X-Title": "CodeWeave",
            },
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"LLM stream error: {body.decode()[:500]}",
                )
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming chat endpoint. Returns complete answer with source citations."""
    import uuid

    # 1. Rate limiting (user_id=None for now — update once auth middleware is wired)
    try:
        rate_limiter = get_rate_limiter()
        await rate_limiter.check_all(user_id=None)
    except HTTPException:
        raise
    except RuntimeError:
        pass  # Rate limiter not initialised (dev mode) — allow through

    # 2. Check repository exists and is ingested
    repo_result = await db.execute(
        select(Repository).where(Repository.id == request.repository_id)
    )
    repository = repo_result.scalar_one_or_none()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repository.ingestion_status != IngestionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Repository ingestion is {repository.ingestion_status.value}. Wait for it to complete.",
        )

    # 3. Check LLM response cache
    try:
        cache = get_cache()
        cached = await cache.get_llm_response(request.question, request.repository_id)
        if cached:
            return ChatResponse(**cached)
    except RuntimeError:
        cache = None  # Cache not initialised

    # 4. Retrieve relevant chunks
    retrieval = RetrievalService(db, cache=cache)
    chunks = await retrieval.search(
        query=request.question,
        repository_id=request.repository_id,
        top_k=5,
    )

    context = retrieval.build_context(chunks)

    # 5. Build prompt
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=(
                f"Repository: {repository.full_name}\n\n"
                f"Context from codebase:\n{context}\n\n"
                f"Question: {request.question}"
            ),
        ),
    ]

    # 6. Call LLM with cost tracking
    llm = get_llm_provider()
    tracker = CostTracker(db)
    conversation_id = request.conversation_id or str(uuid.uuid4())

    async with TimedLLMCall(tracker, model=settings.DEFAULT_MODEL, endpoint="chat") as t:
        try:
            response = await llm.chat(messages, temperature=0.3, max_tokens=2000)
            t.set_usage(response.usage or {})
        except Exception as e:
            t.mark_failure()
            logger.error("LLM call failed: %s", e)
            # Graceful degradation — return a meaningful error
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable. Please try again shortly.",
            )

    # 7. Build response
    source_chunks = [
        SourceChunk(
            source=c.source,
            content=c.content[:300] + ("..." if len(c.content) > 300 else ""),
            relevance_score=round(c.score, 3),
        )
        for c in chunks
    ]

    result = ChatResponse(
        answer=response.content,
        sources=source_chunks,
        conversation_id=conversation_id,
        model_used=response.model,
    )

    # 8. Cache the response
    if cache:
        await cache.set_llm_response(
            request.question,
            request.repository_id,
            result.model_dump(),
        )

    return result


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming chat endpoint. Returns chunks as they arrive from the LLM."""

    # 1. Rate limiting
    try:
        rate_limiter = get_rate_limiter()
        await rate_limiter.check_all(user_id=None)
    except HTTPException:
        raise
    except RuntimeError:
        pass

    # 2. Validate repo
    repo_result = await db.execute(
        select(Repository).where(Repository.id == request.repository_id)
    )
    repository = repo_result.scalar_one_or_none()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repository.ingestion_status != IngestionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Repository not yet ingested")

    # 3. Retrieve chunks
    try:
        cache = get_cache()
    except RuntimeError:
        cache = None
    retrieval = RetrievalService(db, cache=cache)
    chunks = await retrieval.search(
        query=request.question,
        repository_id=request.repository_id,
        top_k=5,
    )
    context = retrieval.build_context(chunks)

    # 4. Build prompt
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=(
                f"Repository: {repository.full_name}\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {request.question}"
            ),
        ),
    ]

    # 5. Build source metadata JSON (sent first as a special SSE event)
    sources_json = json.dumps([
        {"source": c.source, "score": round(c.score, 3)}
        for c in chunks
    ])

    async def event_generator():
        # First event: source citations
        yield f"event: sources\ndata: {sources_json}\n\n"

        # Stream LLM tokens
        try:
            async for token in _stream_llm_response(messages, settings.DEFAULT_MODEL):
                # Escape newlines in SSE data
                escaped = token.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
        except Exception as e:
            logger.error("Streaming LLM error: %s", e)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        # Final done event
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/usage")
async def get_usage(db: AsyncSession = Depends(get_db)):
    """Return today's LLM usage stats."""
    try:
        rate_limiter = get_rate_limiter()
        stats = await rate_limiter.get_user_usage(user_id=1)  # TODO: use real user_id
        return stats
    except RuntimeError:
        return {"detail": "Usage tracking not available"}
