"""Test Runner Tool — sandboxed test execution for the autonomous agent."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

MAX_OUTPUT_CHARS = 10_000
DEFAULT_TIMEOUT = 60  # seconds


class TestRunnerTool:
    """Tool: run tests in the repository.

    For MVP: runs tests directly via subprocess.
    For production: should use Docker sandbox with resource limits:
      --network none --memory 512m --cpus 1.0 --read-only
    """

    name = "run_tests"
    description = "Run the test suite (or specific test file) and return results."
    parameters = {
        "test_path": {"type": "string", "description": "Specific test file or directory (optional)"},
        "framework": {"type": "string", "description": "'pytest', 'npm', or 'auto' (default)"},
    }

    def __init__(self, repo_path: Path):
        self._repo_path = repo_path

    async def execute(
        self,
        test_path: Optional[str] = None,
        framework: str = "auto",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> str:
        """Run tests and return the output."""
        if framework == "auto":
            framework = self._detect_framework()

        if framework == "pytest":
            cmd = ["python", "-m", "pytest", "--timeout=30", "-x", "-q", "--tb=short", "--no-header"]
            if test_path:
                cmd.append(test_path)
        elif framework == "npm":
            cmd = ["npm", "test", "--", "--watchAll=false"]
            if test_path:
                cmd.extend(["--testPathPattern", test_path])
        else:
            return f"Unknown test framework: {framework}"

        logger.info("Running tests: %s (timeout=%ds)", " ".join(cmd), timeout)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self._repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return (
                    f"TIMEOUT: Test execution exceeded {timeout}s limit and was killed.\n"
                    "Consider reducing the test scope or increasing the timeout."
                )

            output = ""
            if stdout:
                output += stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n--- STDERR ---\n" + stderr.decode("utf-8", errors="replace")

            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS] + f"\n\n[...truncated at {MAX_OUTPUT_CHARS} chars...]"

            exit_code = proc.returncode
            status = "PASSED" if exit_code == 0 else "FAILED"
            header = f"Test Result: {status} (exit code {exit_code})\n{'=' * 50}\n"

            return header + output

        except FileNotFoundError:
            return f"Error: Command not found. Make sure '{cmd[0]}' is installed."
        except Exception as e:
            logger.error("TestRunnerTool error: %s", e)
            return f"Test execution failed: {e}"

    def _detect_framework(self) -> str:
        """Auto-detect the test framework based on repo files."""
        if (self._repo_path / "pytest.ini").exists() or \
           (self._repo_path / "setup.cfg").exists() or \
           (self._repo_path / "pyproject.toml").exists() or \
           (self._repo_path / "requirements.txt").exists():
            return "pytest"
        if (self._repo_path / "package.json").exists():
            return "npm"
        return "pytest"
