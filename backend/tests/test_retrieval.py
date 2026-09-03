"""Tests for RetrievalService.

Tests the retrieval pipeline logic (context building, chunk formatting)
without requiring a live PostgreSQL database. Database-dependent vector
search is tested via mocking the DB session.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.services.retrieval import RetrievalService, RetrievedChunk


# ---------------------------------------------------------------------------
# RetrievedChunk unit tests
# ---------------------------------------------------------------------------

class TestRetrievedChunk:
    """Tests for the RetrievedChunk dataclass."""

    def test_creation(self):
        chunk = RetrievedChunk(
            content="def hello(): pass",
            source="app/main.py",
            chunk_type="function",
            language="python",
            score=0.92,
            document_id=1,
        )
        assert chunk.content == "def hello(): pass"
        assert chunk.source == "app/main.py"
        assert chunk.chunk_type == "function"
        assert chunk.language == "python"
        assert chunk.score == 0.92
        assert chunk.document_id == 1

    def test_low_score_chunk(self):
        chunk = RetrievedChunk(
            content="config file",
            source="config.yaml",
            chunk_type="config",
            language=None,
            score=0.05,
            document_id=2,
        )
        assert chunk.language is None
        assert chunk.score < 0.10


# ---------------------------------------------------------------------------
# build_context tests
# ---------------------------------------------------------------------------

class TestBuildContext:
    """Tests for RetrievalService.build_context static method."""

    def test_empty_chunks(self):
        result = RetrievalService.build_context([])
        assert result == ""

    def test_single_chunk(self):
        chunk = RetrievedChunk(
            content="def add(a, b): return a + b",
            source="math.py",
            chunk_type="function",
            language="python",
            score=0.95,
            document_id=1,
        )
        result = RetrievalService.build_context([chunk])
        assert "math.py" in result
        assert "def add(a, b)" in result
        assert "score=0.95" in result

    def test_multiple_chunks_ordered(self):
        chunks = [
            RetrievedChunk(
                content="First chunk content",
                source="first.py",
                chunk_type="function",
                language="python",
                score=0.90,
                document_id=1,
            ),
            RetrievedChunk(
                content="Second chunk content",
                source="second.py",
                chunk_type="class",
                language="python",
                score=0.80,
                document_id=2,
            ),
        ]
        result = RetrievalService.build_context(chunks)
        # Both chunks should appear
        assert "First chunk content" in result
        assert "Second chunk content" in result
        # Source headers should appear in order
        first_pos = result.index("first.py")
        second_pos = result.index("second.py")
        assert first_pos < second_pos

    def test_token_budget_truncation(self):
        """Verify that build_context respects the max_tokens budget."""
        large_content = "x" * 10000  # Very large chunk
        chunk = RetrievedChunk(
            content=large_content,
            source="big.py",
            chunk_type="text",
            language="python",
            score=0.99,
            document_id=1,
        )
        # 100 tokens ≈ 400 chars budget
        result = RetrievalService.build_context([chunk], max_tokens=100)
        # Result should be significantly shorter than 10000 chars
        assert len(result) < 1000

    def test_multiple_chunks_budget(self):
        """When budget is tight, later chunks may be dropped."""
        chunks = [
            RetrievedChunk(
                content="A" * 2000,
                source="a.py",
                chunk_type="text",
                language="python",
                score=0.90,
                document_id=1,
            ),
            RetrievedChunk(
                content="B" * 2000,
                source="b.py",
                chunk_type="text",
                language="python",
                score=0.80,
                document_id=2,
            ),
        ]
        # Budget of 500 tokens = 2000 chars — enough for first chunk only
        result = RetrievalService.build_context(chunks, max_tokens=500)
        assert "a.py" in result
        # Second chunk may be partially included or dropped
        assert len(result) <= 2500  # Reasonable bound


# ---------------------------------------------------------------------------
# Search method tests (mocked DB)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService to prevent loading actual models during tests."""
    with patch("app.services.retrieval.EmbeddingService.get_instance") as mock:
        mock_instance = MagicMock()
        mock_instance.aencode = AsyncMock(return_value=[0.1] * 384)
        mock.return_value = mock_instance
        yield mock

class TestRetrievalSearch:
    """Tests for the search method using mocked database sessions."""

    @pytest.mark.asyncio
    async def test_search_semantic_only(self, mock_embedding_service):
        mock_vec_row = MagicMock(id=1, content="def semantic(): pass", source="semantic.py", chunk_type="function", language="python", score=0.85)
        mock_db = AsyncMock()
        async def db_execute(sql, params):
            mock_result = MagicMock()
            if "embedding <=>" in str(sql):
                mock_result.fetchall.return_value = [mock_vec_row]
            else:
                mock_result.fetchall.return_value = []
            return mock_result
        mock_db.execute.side_effect = db_execute
        service = RetrievalService(db=mock_db, cache=None)
        chunks = await service.search("semantic function", repository_id=1)
        assert len(chunks) == 1
        assert chunks[0].document_id == 1
        assert chunks[0].score == 0.85

    @pytest.mark.asyncio
    async def test_search_keyword_only(self, mock_embedding_service):
        mock_kw_row = MagicMock(id=2, content="def exact_match(): pass", source="exact.py", chunk_type="function", language="python")
        mock_db = AsyncMock()
        async def db_execute(sql, params):
            mock_result = MagicMock()
            if "embedding <=>" in str(sql):
                mock_result.fetchall.return_value = []
            else:
                mock_result.fetchall.return_value = [mock_kw_row]
            return mock_result
        mock_db.execute.side_effect = db_execute
        service = RetrievalService(db=mock_db, cache=None)
        chunks = await service.search("exact_match", repository_id=1)
        assert len(chunks) == 1
        assert chunks[0].document_id == 2
        assert chunks[0].score == 0.6  # The hardcoded keyword score

    @pytest.mark.asyncio
    async def test_search_duplicate_merging(self, mock_embedding_service):
        mock_vec_row = MagicMock(id=3, content="def merge(): pass", source="merge.py", chunk_type="function", language="python", score=0.85)
        mock_kw_row = MagicMock(id=3, content="def merge(): pass", source="merge.py", chunk_type="function", language="python")
        mock_db = AsyncMock()
        async def db_execute(sql, params):
            mock_result = MagicMock()
            if "embedding <=>" in str(sql):
                mock_result.fetchall.return_value = [mock_vec_row]
            else:
                mock_result.fetchall.return_value = [mock_kw_row]
            return mock_result
        mock_db.execute.side_effect = db_execute
        service = RetrievalService(db=mock_db, cache=None)
        chunks = await service.search("merge function", repository_id=1)
        assert len(chunks) == 1
        assert chunks[0].document_id == 3
        assert chunks[0].score == 0.85  # Max of 0.85 and 0.6

    @pytest.mark.asyncio
    async def test_search_exact_identifier_pattern_ops(self, mock_embedding_service):
        """Test that exact identifier like pattern_ops is retrievable even if vector score is low."""
        mock_vec_row = MagicMock(id=4, content="some unrelated pattern", source="unrelated.py", chunk_type="text", language="python", score=0.90)
        mock_kw_row = MagicMock(id=5, content="pattern_ops = {}", source="operations.py", chunk_type="function", language="python")
        mock_db = AsyncMock()
        async def db_execute(sql, params):
            mock_result = MagicMock()
            if "embedding <=>" in str(sql):
                mock_result.fetchall.return_value = [mock_vec_row]
            else:
                assert "kw0" in params
                assert params["kw0"] == "%pattern_ops%"
                mock_result.fetchall.return_value = [mock_kw_row]
            return mock_result
        mock_db.execute.side_effect = db_execute
        service = RetrievalService(db=mock_db, cache=None)
        chunks = await service.search("pattern_ops", repository_id=1)
        assert len(chunks) == 2
        # Sort order: 0.90 from vector first, 0.6 from keyword second.
        assert chunks[0].document_id == 4
        assert chunks[1].document_id == 5
        
    @pytest.mark.asyncio
    async def test_search_respects_top_k(self, mock_embedding_service):
        mock_db = AsyncMock()
        async def db_execute(sql, params):
            assert params["top_k"] <= 10
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            return mock_result
        mock_db.execute.side_effect = db_execute
        service = RetrievalService(db=mock_db, cache=None)
        await service.search("test", repository_id=1, top_k=999)

    @pytest.mark.asyncio
    async def test_search_filters_low_scores(self, mock_embedding_service):
        mock_vec_row = MagicMock(id=1, content="irrelevant", source="junk.py", chunk_type="text", language="python", score=0.10)
        mock_db = AsyncMock()
        async def db_execute(sql, params):
            mock_result = MagicMock()
            if "embedding <=>" in str(sql):
                mock_result.fetchall.return_value = [mock_vec_row]
            else:
                mock_result.fetchall.return_value = []
            return mock_result
        mock_db.execute.side_effect = db_execute
        service = RetrievalService(db=mock_db, cache=None)
        chunks = await service.search("something specific", repository_id=1)
        assert len(chunks) == 0
