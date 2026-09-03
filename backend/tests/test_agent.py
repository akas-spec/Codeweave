"""Tests for the AgentOrchestrator.

Tests the ReAct loop logic, JSON tool parsing, iteration limits,
and session management — all with mocked LLM and tools so no
real API calls or subprocesses are executed.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent import (
    AgentOrchestrator,
    AgentSession,
    ToolCall,
    MAX_ITERATIONS,
    MAX_LLM_CALLS,
)


# ---------------------------------------------------------------------------
# AgentSession unit tests
# ---------------------------------------------------------------------------

class TestAgentSession:
    """Tests for the AgentSession dataclass."""

    def test_defaults(self):
        session = AgentSession()
        assert session.status == "running"
        assert session.iterations == 0
        assert session.llm_calls == 0
        assert session.patch_attempts == 0
        assert session.test_runs == 0
        assert len(session.job_id) == 8

    def test_unique_job_ids(self):
        s1 = AgentSession()
        s2 = AgentSession()
        assert s1.job_id != s2.job_id

    def test_is_within_limits_fresh(self):
        session = AgentSession()
        within, reason = session.is_within_limits()
        assert within is True
        assert reason == ""

    def test_is_within_limits_max_iterations(self):
        session = AgentSession()
        session.iterations = MAX_ITERATIONS
        within, reason = session.is_within_limits()
        assert within is False
        assert "iterations" in reason.lower()

    def test_is_within_limits_max_llm_calls(self):
        session = AgentSession()
        session.llm_calls = MAX_LLM_CALLS
        within, reason = session.is_within_limits()
        assert within is False
        assert "llm" in reason.lower()


# ---------------------------------------------------------------------------
# ToolCall unit tests
# ---------------------------------------------------------------------------

class TestToolCall:
    """Tests for the ToolCall dataclass."""

    def test_successful_call(self):
        tc = ToolCall(tool="search_code", args={"query": "hello"}, output="found 3 results", success=True)
        assert tc.tool == "search_code"
        assert tc.success is True

    def test_failed_call(self):
        tc = ToolCall(tool="run_tests", args={}, output="timeout", success=False)
        assert tc.success is False


# ---------------------------------------------------------------------------
# JSON parsing tests
# ---------------------------------------------------------------------------

class TestJsonParsing:
    """Test that the agent can extract JSON tool calls from LLM output."""

    def test_parse_clean_json(self):
        """Standard JSON response."""
        raw = json.dumps({
            "thought": "I should search the codebase",
            "tool": "search_code",
            "args": {"query": "authentication", "top_k": 5}
        })
        parsed = json.loads(raw)
        assert parsed["tool"] == "search_code"
        assert parsed["args"]["query"] == "authentication"

    def test_parse_json_with_markdown_backticks(self):
        """LLMs often wrap JSON in ```json ... ``` blocks."""
        raw = '```json\n{"thought": "searching", "tool": "search_code", "args": {"query": "auth"}}\n```'
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        parsed = json.loads(cleaned)
        assert parsed["tool"] == "search_code"

    def test_parse_done_action(self):
        """The 'done' tool signals task completion."""
        raw = json.dumps({
            "thought": "Fix applied and tests pass",
            "tool": "done",
            "args": {"status": "completed", "summary": "Fixed the bug in add.py"}
        })
        parsed = json.loads(raw)
        assert parsed["tool"] == "done"
        assert parsed["args"]["status"] == "completed"

    def test_invalid_json_raises(self):
        """Malformed JSON should raise."""
        raw = '{"tool": "search_code", BROKEN'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)


# ---------------------------------------------------------------------------
# AgentOrchestrator._parse_response tests
# ---------------------------------------------------------------------------

class TestParseResponse:
    """Test the _parse_response method directly."""

    def _make_orchestrator(self):
        """Create an orchestrator with fully mocked dependencies."""
        with patch("app.services.agent.get_llm_provider") as mock_llm, \
             patch("app.services.agent.CostTracker"), \
             patch("app.services.agent.SearchCodeTool"), \
             patch("app.services.agent.TestRunnerTool"), \
             patch("app.services.agent.PatchApplierTool"), \
             patch("app.services.agent.GitOpsTool"):

            mock_db = AsyncMock()
            mock_repo = MagicMock()
            mock_repo.id = 1
            mock_repo.full_name = "test/repo"

            orchestrator = AgentOrchestrator(
                db=mock_db,
                repository=mock_repo,
                repo_path=Path("C:/tmp/test-repo"),
                access_token="mock-token",
            )
        return orchestrator

    def test_parse_valid_json(self):
        orch = self._make_orchestrator()
        result = orch._parse_response('{"thought": "test", "tool": "done", "args": {}}')
        assert result is not None
        assert result["tool"] == "done"

    def test_parse_json_in_backticks(self):
        orch = self._make_orchestrator()
        result = orch._parse_response('```json\n{"thought": "t", "tool": "done", "args": {}}\n```')
        assert result is not None
        assert result["tool"] == "done"

    def test_parse_invalid_json_returns_none(self):
        orch = self._make_orchestrator()
        result = orch._parse_response("This is not JSON at all")
        assert result is None

    def test_parse_empty_returns_none(self):
        orch = self._make_orchestrator()
        result = orch._parse_response("")
        assert result is None


# ---------------------------------------------------------------------------
# Agent orchestration tests (mocked LLM + tools)
# ---------------------------------------------------------------------------

class TestAgentOrchestration:
    """Integration-style tests for the agent's ReAct loop with mocked dependencies."""

    def _make_llm_response(self, thought: str, tool: str, args: dict):
        """Helper to create a JSON response string from the mock LLM."""
        return json.dumps({"thought": thought, "tool": tool, "args": args})

    @pytest.mark.asyncio
    async def test_agent_completes_on_done(self):
        """Agent should stop when the LLM returns the 'done' tool."""
        done_response = self._make_llm_response(
            thought="Task is complete",
            tool="done",
            args={"status": "completed", "summary": "All good"}
        )

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(content=done_response, usage={}))

        mock_tracker_instance = MagicMock()
        mock_tracker_instance.__aenter__ = AsyncMock(return_value=MagicMock(set_usage=MagicMock()))
        mock_tracker_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.agent.get_llm_provider", return_value=mock_llm), \
             patch("app.services.agent.CostTracker"), \
             patch("app.services.agent.TimedLLMCall", return_value=mock_tracker_instance), \
             patch("app.services.agent.SearchCodeTool"), \
             patch("app.services.agent.TestRunnerTool"), \
             patch("app.services.agent.PatchApplierTool"), \
             patch("app.services.agent.GitOpsTool"):

            mock_db = AsyncMock()
            mock_repo = MagicMock()
            mock_repo.id = 1
            mock_repo.full_name = "test/repo"

            orchestrator = AgentOrchestrator(
                db=mock_db,
                repository=mock_repo,
                repo_path=Path("C:/tmp/test-repo"),
                access_token="mock-token",
            )
            session = await orchestrator.run("Fix the bug")

        assert session.status == "completed"
        assert session.iterations >= 1

    @pytest.mark.asyncio
    async def test_agent_search_then_done(self):
        """Agent searches code, then calls done."""
        search_response = self._make_llm_response(
            thought="Let me search for the bug",
            tool="search_code",
            args={"query": "broken function"}
        )
        done_response = self._make_llm_response(
            thought="Found the issue, marking done",
            tool="done",
            args={"status": "completed", "summary": "Identified the bug"}
        )

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(
            side_effect=[
                MagicMock(content=search_response, usage={}),
                MagicMock(content=done_response, usage={}),
            ]
        )

        mock_tracker_instance = MagicMock()
        mock_tracker_instance.__aenter__ = AsyncMock(return_value=MagicMock(set_usage=MagicMock()))
        mock_tracker_instance.__aexit__ = AsyncMock(return_value=False)

        mock_search_execute = AsyncMock(return_value="Found: def broken(): return x - y")

        with patch("app.services.agent.get_llm_provider", return_value=mock_llm), \
             patch("app.services.agent.CostTracker"), \
             patch("app.services.agent.TimedLLMCall", return_value=mock_tracker_instance), \
             patch("app.services.agent.SearchCodeTool") as MockSearchCls, \
             patch("app.services.agent.TestRunnerTool"), \
             patch("app.services.agent.PatchApplierTool"), \
             patch("app.services.agent.GitOpsTool"):

            MockSearchCls.return_value.execute = mock_search_execute

            mock_db = AsyncMock()
            mock_repo = MagicMock()
            mock_repo.id = 1
            mock_repo.full_name = "test/repo"

            orchestrator = AgentOrchestrator(
                db=mock_db,
                repository=mock_repo,
                repo_path=Path("C:/tmp/test-repo"),
                access_token="mock-token",
            )
            session = await orchestrator.run("Find the bug")

        assert session.status == "completed"
        assert session.iterations == 2
