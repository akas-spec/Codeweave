import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.repository import Repository
from app.services.llm.base import ChatMessage, LLMResponse, get_llm_provider
from app.services.cost_tracker import CostTracker, TimedLLMCall
from app.tools.search_code import SearchCodeTool
from app.tools.test_runner import TestRunnerTool
from app.tools.patch_applier import PatchApplierTool
from app.tools.git_ops import GitOpsTool

logger = logging.getLogger(__name__)

# Hard limits
MAX_ITERATIONS = 10
MAX_LLM_CALLS = 20
MAX_PATCH_ATTEMPTS = 3
MAX_TEST_RUNS = 5
SESSION_TIMEOUT = 600  # 10 minutes


AGENT_SYSTEM_PROMPT = """You are CodeWeave Agent, an autonomous software engineer.
You fix bugs and implement changes in code repositories.

You have access to the following tools:

1. **search_code(query, file_pattern, top_k)**: Search the codebase semantically to find relevant code. Use file_pattern to filter by file path.
2. **run_tests(test_path, framework)**: Run the test suite to check if code passes.
3. **apply_patch(file_path, mode, content, search, replace)**: Apply code changes.
   - mode="write": Write full file content
   - mode="patch": Search-and-replace in a file  
4. **git_ops(action, branch_name, message, body, base_branch)**: Git operations.
   - action="create_branch": Create and checkout a new branch
   - action="commit": Stage all changes and commit
   - action="push": Push branch to origin
   - action="create_pr": Create a Pull Request on GitHub

Workflow:
1. First, understand the issue by searching the codebase.
2. Plan your fix step by step.
3. Apply the patch(es).
4. Run tests to verify.
5. Once tests pass and the task is complete, immediately call \'done\'. (You may commit/push if explicitly asked).

Always respond with a JSON object containing ONE tool call:
```json
{
  "thought": "Your reasoning about what to do next",
  "tool": "tool_name",
  "args": { ... tool arguments ... }
}
```

When you are done (fix applied and PR created, or you cannot fix it), respond with:
```json
{
  "thought": "Summary of what was done",
  "tool": "done",
  "args": { "status": "completed" or "failed", "summary": "..." }
}
```

Rules:
- Only modify files related to the issue.
- Never delete files unless explicitly asked.
- Always run tests after applying patches.
- If tests fail 3 times, stop and report the issue.
- Keep changes minimal and focused.
- IMPORTANT: search_code adds headers like "# File: path/to/file" to its output. These are metadata, NOT actual file contents. DO NOT include these headers in your 'search' string for apply_patch.
- ENVIRONMENT ERRORS: If run_tests returns a usage error, command not found, missing plugin (e.g. pytest-timeout), or other environment issue, DO NOT retry the tests. It will not fix the environment. Immediately call 'done' and report the environment failure.
- TEST PATHS: Verify the requested test path exists before calling run_tests. If tests fail because of a missing/nonexistent test file, do not repeatedly retry; find a valid relevant test once.
- TEST FAILURES: If a valid test run fails, inspect the failure. If the failure is unrelated to your patch/environment, call 'done' and report it. Retry only when the failure is actionable and reasonably fixable by you.
- DONE PREFERENCE: Once a relevant test passes and the requested task is satisfied, immediately call 'done'. Do not make unnecessary additional tool calls (like creating a branch or PR if not explicitly required).
"""


@dataclass
class ToolCall:
    tool: str
    args: dict
    output: str
    success: bool


@dataclass
class AgentSession:
    """Tracks the state of an autonomous agent run."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "running"           # running, completed, failed, max_iterations_reached
    iterations: int = 0
    llm_calls: int = 0
    patch_attempts: int = 0
    test_runs: int = 0
    tool_calls: list = field(default_factory=list)
    messages: list = field(default_factory=list)  # Conversation history
    patch_diff: Optional[str] = None
    pr_url: Optional[str] = None
    summary: str = ""
    start_time: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    def is_within_limits(self) -> tuple[bool, str]:
        """Check if the session is still within all hard limits."""
        if self.iterations >= MAX_ITERATIONS:
            return False, f"Max iterations ({MAX_ITERATIONS}) reached"
        if self.llm_calls >= MAX_LLM_CALLS:
            return False, f"Max LLM calls ({MAX_LLM_CALLS}) reached"
        if self.elapsed > SESSION_TIMEOUT:
            return False, f"Session timeout ({SESSION_TIMEOUT}s) exceeded"
        return True, ""


class AgentOrchestrator:
    """ReAct agent loop: Observe → Think → Act → Observe.
    
    Orchestrates tool calls to autonomously fix an issue in a repository.
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Repository,
        repo_path: Path,
        access_token: Optional[str] = None,
    ):
        self._db = db
        self._repository = repository
        self._repo_path = repo_path
        self._llm = get_llm_provider()
        self._tracker = CostTracker(db)

        # Initialize tools
        self._tools = {
            "search_code": SearchCodeTool(db, repository.id),
            "run_tests": TestRunnerTool(repo_path),
            "apply_patch": PatchApplierTool(repo_path),
            "git_ops": GitOpsTool(
                repo_path=repo_path,
                github_token=access_token,
                repo_full_name=repository.full_name,
            ),
        }

    async def run(self, issue_description: str, file_hint: Optional[str] = None) -> AgentSession:
        """Execute the full autonomous fix loop.
        
        Returns an AgentSession with the results.
        """
        session = AgentSession()

        # Initialize conversation
        session.messages = [
            ChatMessage(role="system", content=AGENT_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    f"Repository: {self._repository.full_name}\n"
                    f"Issue: {issue_description}\n"
                    + (f"File hint: {file_hint}\n" if file_hint else "")
                    + "\nPlease fix this issue. Start by searching the codebase to understand the problem."
                ),
            ),
        ]

        logger.info(
            "Agent session %s started for repo %s: %s",
            session.job_id, self._repository.full_name, issue_description[:100],
        )

        while True:
            # Check limits
            within, reason = session.is_within_limits()
            if not within:
                session.status = "max_iterations_reached"
                session.summary = f"Agent stopped: {reason}"
                logger.warning("Agent %s stopped: %s", session.job_id, reason)
                break

            session.iterations += 1

            # Call LLM for next action
            try:
                async with TimedLLMCall(
                    self._tracker,
                    model=settings.DEFAULT_MODEL,
                    endpoint="agent",
                ) as t:
                    response = await self._llm.chat(
                        session.messages,
                        temperature=0.2,  # Low temperature for deterministic actions
                        max_tokens=2000,
                    )
                    t.set_usage(response.usage or {})
                    session.llm_calls += 1

            except Exception as e:
                logger.error("Agent LLM call failed: %s", e)
                session.status = "failed"
                session.summary = f"LLM call failed: {e}"
                break

            # Parse the LLM response
            parsed = self._parse_response(response.content)
            if parsed is None:
                # Limit invalid parse retries
                invalid_count = sum(1 for m in session.messages if m.content and "Your response was not valid JSON" in m.content)
                if invalid_count >= 3:
                    session.status = "failed"
                    session.summary = "Agent failed to output valid JSON repeatedly."
                    break

                # LLM returned invalid JSON — ask it to fix
                session.messages.append(ChatMessage(role="assistant", content=response.content or ""))
                session.messages.append(ChatMessage(
                    role="user",
                    content="Your response was not valid JSON. Please respond with a JSON object containing 'thought', 'tool', and 'args'.",
                ))
                continue

            thought = parsed.get("thought", "")
            tool_name = parsed.get("tool", "")
            tool_args = parsed.get("args", {})

            safe_thought = thought[:100].encode('ascii', 'replace').decode('ascii')
            logger.info(
                "Agent %s iter %d: tool=%s thought=%s",
                session.job_id, session.iterations, tool_name, safe_thought,
            )

            # Check for "done" signal
            if tool_name == "done":
                session.status = tool_args.get("status", "completed")
                session.summary = tool_args.get("summary", thought)
                break

            # Check for repeated failed tool calls to prevent infinite loops
            is_duplicate = False
            
            # Find last successful repository state change
            last_state_change = -1
            for i, prev_tc in enumerate(session.tool_calls):
                if prev_tc.success and prev_tc.tool in ('apply_patch', 'git_ops'):
                    last_state_change = i
                    
            for i, prev_tc in enumerate(session.tool_calls):
                if prev_tc.tool == tool_name and prev_tc.args == tool_args and not prev_tc.success:
                    # If this is run_tests and the repo state changed since the failure, it's not a duplicate
                    if tool_name == 'run_tests' and last_state_change > i:
                        continue
                    is_duplicate = True
                    break
            
            if is_duplicate:
                tool_output = "Error: You already tried this exact tool call with these exact arguments and it failed. Do NOT repeat the exact same action. Try a different approach, fix the underlying issue, or call the 'done' tool to report failure."
            else:
                # Execute tool
                tool_output = await self._execute_tool(session, tool_name, tool_args)

            # Record tool call
            tc = ToolCall(
                tool=tool_name,
                args=tool_args,
                output=tool_output[:2000],  # Truncate for history
                success="Error" not in tool_output and "FAILED" not in tool_output,
            )
            session.tool_calls.append(tc)

            # Track PR URL if created
            if tool_name == "git_ops" and "PR created:" in tool_output:
                session.pr_url = tool_output.split("PR created: ")[1].strip()

            # Add to conversation history
            session.messages.append(ChatMessage(role="assistant", content=response.content))
            session.messages.append(ChatMessage(
                role="user",
                content=f"Tool result ({tool_name}):\n{tool_output}",
            ))

            # Sliding window: keep conversation manageable
            if len(session.messages) > 24:
                # Keep system prompt + last 20 messages
                session.messages = [session.messages[0]] + session.messages[-20:]

        logger.info(
            "Agent %s finished: status=%s, iterations=%d, llm_calls=%d",
            session.job_id, session.status, session.iterations, session.llm_calls,
        )

        return session

    async def _execute_tool(self, session: AgentSession, tool_name: str, args: dict) -> str:
        """Execute a tool and return its output string."""
        if tool_name not in self._tools:
            return f"Error: Unknown tool '{tool_name}'. Available: {list(self._tools.keys())}"

        tool = self._tools[tool_name]

        # Enforce sub-limits
        if tool_name == "apply_patch":
            session.patch_attempts += 1
            if session.patch_attempts > MAX_PATCH_ATTEMPTS:
                return f"Error: Max patch attempts ({MAX_PATCH_ATTEMPTS}) exceeded. Stop patching and report."

        if tool_name == "run_tests":
            session.test_runs += 1
            if session.test_runs > MAX_TEST_RUNS:
                return f"Error: Max test runs ({MAX_TEST_RUNS}) exceeded. Stop testing and report."

        try:
            return await tool.execute(**args)
        except TypeError as e:
            return f"Error: Invalid arguments for {tool_name}: {e}"
        except Exception as e:
            logger.error("Tool %s execution error: %s", tool_name, e)
            return f"Error executing {tool_name}: {e}"

    @staticmethod
    def _parse_response(content: Optional[str]) -> Optional[dict]:
        """Parse the LLM response as JSON. Returns None if invalid."""
        if not content:
            return None
            
        content = content.strip()

        # Try to extract JSON from markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
            else:
                content = content[start:].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
            else:
                content = content[start:].strip()

        # Try direct JSON parse
        try:
            parsed = json.loads(content, strict=False)
            if isinstance(parsed, dict) and "tool" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
        brace_start = content.find("{")
        brace_end = content.rfind("}") + 1
        if brace_start >= 0 and brace_end > brace_start:
            try:
                parsed = json.loads(content[brace_start:brace_end], strict=False)
                if isinstance(parsed, dict) and "tool" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        return None
