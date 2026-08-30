import pytest
from pathlib import Path
from app.services.ingestion import IngestionService, Chunk
from app.services.github_service import GitHubService


def test_parse_github_url_https():
    owner, repo = GitHubService.parse_github_url("https://github.com/owner/repo")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_github_url_with_git():
    owner, repo = GitHubService.parse_github_url("https://github.com/owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_github_url_invalid():
    with pytest.raises(ValueError):
        GitHubService.parse_github_url("not-a-url")


def test_ext_to_language():
    assert IngestionService._ext_to_language(".py") == "python"
    assert IngestionService._ext_to_language(".js") == "javascript"
    assert IngestionService._ext_to_language(".ts") == "typescript"
    assert IngestionService._ext_to_language(".go") == "go"
    assert IngestionService._ext_to_language(".unknown") == "unknown"


def test_chunk_dataclass():
    chunk = Chunk(
        content="def hello(): pass",
        source="test.py",
        chunk_index=0,
        chunk_type="function",
        language="python",
    )
    assert chunk.content == "def hello(): pass"
    assert chunk.source == "test.py"
    assert chunk.chunk_type == "function"
