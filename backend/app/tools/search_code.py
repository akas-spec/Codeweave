"""Search Code Tool — semantic vector search for the autonomous agent."""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)


class SearchCodeTool:
    """Tool: search the codebase using semantic vector search.

    The agent calls this to find relevant code for understanding or fixing issues.
    """

    name = "search_code"
    description = "Search the codebase semantically. Returns the most relevant code chunks for a query."
    parameters = {
        "query": {"type": "string", "description": "Natural language query describing what code to find"},
        "file_pattern": {"type": "string", "description": "Optional substring to filter results by file path"},
        "top_k": {"type": "integer", "description": "Number of results to return (default 5, max 10)"},
    }

    def __init__(self, db: AsyncSession, repository_id: int):
        self._db = db
        self._repo_id = repository_id
        self._retrieval = RetrievalService(db)

    async def execute(self, query: str, file_pattern: Optional[str] = None, top_k: int = 5) -> str:
        """Execute the search and return formatted results."""
        top_k = min(max(top_k, 1), 10)
        fetch_k = top_k * 3 if file_pattern else top_k
        try:
            chunks = await self._retrieval.search(
                query=query,
                repository_id=self._repo_id,
                top_k=fetch_k,
            )
            
            if file_pattern:
                import fnmatch
                pat = file_pattern.replace("\\", "/").lower()
                glob_pat = pat.replace("/**/", "*").replace("**/", "*").replace("**", "*")
                
                filtered = []
                for c in chunks:
                    src = c.source.replace("\\", "/").lower()
                    if pat in src or fnmatch.fnmatch(src, glob_pat) or fnmatch.fnmatch(src, f"*{glob_pat}"):
                        filtered.append(c)
                chunks = filtered[:top_k]

            if not chunks:
                return "No relevant code found for this query."

            results = []
            for i, chunk in enumerate(chunks, 1):
                content = chunk.content
                file_header = f"# File: {chunk.source}\n\n"
                source_header = f"# Source: {chunk.source}\n\n"
                
                if content.startswith(file_header):
                    content = content[len(file_header):]
                elif content.startswith(source_header):
                    content = content[len(source_header):]

                results.append(
                    f"--- Result {i} ---\n"
                    f"File: {chunk.source}\n"
                    f"Type: {chunk.chunk_type}\n"
                    f"Score: {chunk.score:.2f}\n"
                    f"Content:\n{content}\n"
                )
            return "\n".join(results)
        except Exception as e:
            logger.error("SearchCodeTool error: %s", e)
            return f"Search failed: {e}"
