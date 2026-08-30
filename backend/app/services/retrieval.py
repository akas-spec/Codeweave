import logging
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document
from app.services.embeddings import EmbeddingService
from app.services.cache import CacheService

logger = logging.getLogger(__name__)

MIN_SCORE_THRESHOLD = 0.30   # Cosine similarity floor (0=unrelated, 1=identical)
DEFAULT_TOP_K = 5
MAX_TOP_K = 10


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with its relevance score."""
    content: str
    source: str
    chunk_type: str
    language: Optional[str]
    score: float          # cosine similarity (0–1, higher = more relevant)
    document_id: int


class RetrievalService:
    """Retrieves relevant code/doc chunks from pgvector for a given query.

    Pipeline:
        1. Embed the query (with embedding cache)
        2. Run pgvector cosine similarity search filtered by repo
        3. Filter chunks below MIN_SCORE_THRESHOLD
        4. If zero results, fall back to keyword (SQL LIKE) search
        5. Return top_k RetrievedChunk objects
    """

    def __init__(self, db: AsyncSession, cache: Optional[CacheService] = None):
        self._db = db
        self._cache = cache
        self._embed = EmbeddingService.get_instance()

    async def search(
        self,
        query: str,
        repository_id: int,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[RetrievedChunk]:
        """Return the top_k most relevant chunks for query in repository."""
        top_k = min(top_k, MAX_TOP_K)

        # 1. Get query embedding (check cache first)
        query_embedding = await self._get_query_embedding(query)

        # 2. Vector similarity search
        chunks = await self._vector_search(query_embedding, repository_id, top_k)

        # 3. Filter below threshold
        chunks = [c for c in chunks if c.score >= MIN_SCORE_THRESHOLD]

        # 4. Keyword fallback if no vector results
        if not chunks:
            logger.info("Vector search returned 0 results — falling back to keyword search")
            chunks = await self._keyword_search(query, repository_id, top_k)

        logger.info(
            "Retrieved %d chunks for repo %d (query len=%d chars)",
            len(chunks), repository_id, len(query),
        )
        return chunks

    async def _get_query_embedding(self, query: str) -> list[float]:
        """Return embedding, using cache if available."""
        if self._cache:
            cached = await self._cache.get_embedding(query)
            if cached:
                return cached
        embedding = await self._embed.aencode(query)

        if self._cache:
            await self._cache.set_embedding(query, embedding)

        return embedding

    async def _vector_search(
        self,
        query_embedding: list[float],
        repository_id: int,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Run pgvector ANN search filtered by repository_id."""
        # Convert embedding to pgvector literal format
        vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        sql = text("""
            SELECT
                id,
                content,
                source,
                chunk_type,
                language,
                1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM documents
            WHERE repository_id = :repo_id
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :top_k
        """)

        result = await self._db.execute(sql, {
            "vec": vec_str,
            "repo_id": repository_id,
            "top_k": top_k,
        })
        rows = result.fetchall()

        return [
            RetrievedChunk(
                document_id=row.id,
                content=row.content,
                source=row.source,
                chunk_type=row.chunk_type or "text",
                language=row.language,
                score=float(row.score),
            )
            for row in rows
        ]

    async def _keyword_search(
        self,
        query: str,
        repository_id: int,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Fallback full-text keyword search using SQL ILIKE."""
        # Extract meaningful keywords (skip short words)
        keywords = [w for w in query.split() if len(w) > 3]
        if not keywords:
            return []

        # Build ILIKE conditions for first 3 keywords
        conditions = " OR ".join(
            f"content ILIKE '%{kw}%'" for kw in keywords[:3]
        )
        sql = text(f"""
            SELECT id, content, source, chunk_type, language
            FROM documents
            WHERE repository_id = :repo_id
              AND ({conditions})
            LIMIT :top_k
        """)

        result = await self._db.execute(sql, {"repo_id": repository_id, "top_k": top_k})
        rows = result.fetchall()

        return [
            RetrievedChunk(
                document_id=row.id,
                content=row.content,
                source=row.source,
                chunk_type=row.chunk_type or "text",
                language=row.language,
                score=0.1,   # Low score — keyword match only
            )
            for row in rows
        ]

    @staticmethod
    def build_context(chunks: list[RetrievedChunk], max_tokens: int = 6000) -> str:
        """Format retrieved chunks into a context string for the LLM prompt.

        Respects a rough token budget (1 token ≈ 4 chars).
        """
        budget_chars = max_tokens * 4
        parts = []
        used = 0

        for i, chunk in enumerate(chunks, 1):
            header = f"--- Source {i}: {chunk.source} (score={chunk.score:.2f}) ---\n"
            body = chunk.content.strip()
            section = header + body + "\n"
            if used + len(section) > budget_chars:
                # Truncate last chunk to fit budget
                remaining = budget_chars - used - len(header)
                if remaining > 100:
                    parts.append(header + body[:remaining] + "\n[...truncated...]")
                break
            parts.append(section)
            used += len(section)

        return "\n".join(parts)
