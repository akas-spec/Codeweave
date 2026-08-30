"""Patch Applier Tool — apply code changes for the autonomous agent."""

import logging
import difflib
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PatchApplierTool:
    """Tool: apply code changes to files in the repository.

    Supports two modes:
    - 'write': Write full file content (overwrite or create)
    - 'patch': Apply a search-and-replace patch to a specific file

    Security: Only allows changes within the repository root.
    """

    name = "apply_patch"
    description = "Apply code changes to a file. Use 'write' mode to overwrite, or 'patch' mode to search-and-replace."
    parameters = {
        "file_path": {"type": "string", "description": "Path relative to repo root"},
        "mode": {"type": "string", "description": "'write' or 'patch'"},
        "content": {"type": "string", "description": "For 'write': full file content"},
        "search": {"type": "string", "description": "For 'patch': exact text to find"},
        "replace": {"type": "string", "description": "For 'patch': replacement text"},
    }

    def __init__(self, repo_path: Path):
        self._repo_path = repo_path

    async def execute(
        self,
        file_path: str,
        mode: str = "write",
        content: Optional[str] = None,
        search: Optional[str] = None,
        replace: Optional[str] = None,
    ) -> str:
        """Apply a code change and return a status message."""
        # Security: resolve and validate the path is inside the repo
        target = (self._repo_path / file_path).resolve()
        if not str(target).startswith(str(self._repo_path.resolve())):
            return f"SECURITY ERROR: Path '{file_path}' resolves outside the repository root."

        try:
            if mode == "write":
                return await self._write_file(target, file_path, content)
            elif mode == "patch":
                return await self._patch_file(target, file_path, search, replace)
            else:
                return f"Unknown mode: {mode}. Use 'write' or 'patch'."
        except Exception as e:
            logger.error("PatchApplierTool error: %s", e)
            return f"Failed to apply patch: {e}"

    async def _write_file(self, target: Path, rel_path: str, content: Optional[str]) -> str:
        """Write full content to a file (create or overwrite)."""
        if content is None:
            return "Error: 'content' is required for 'write' mode."

        target.parent.mkdir(parents=True, exist_ok=True)

        old_content = ""
        is_new = not target.exists()
        if not is_new:
            old_content = target.read_text(encoding="utf-8", errors="replace")

        target.write_text(content, encoding="utf-8")

        if is_new:
            return f"Created new file: {rel_path} ({len(content)} chars)"

        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            n=3,
        ))
        additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

        return f"Updated file: {rel_path} (+{additions} -{deletions} lines)"

    async def _patch_file(self, target: Path, rel_path: str, search: Optional[str], replace: Optional[str]) -> str:
        """Search-and-replace in a file."""
        if search is None or replace is None:
            return "Error: 'search' and 'replace' are required for 'patch' mode."

        if not target.exists():
            return f"Error: File not found: {rel_path}"

        original = target.read_text(encoding="utf-8", errors="replace")

        if search not in original:
            return f"Error: Search text not found in {rel_path}. Make sure the search string matches exactly."

        count = original.count(search)
        patched = original.replace(search, replace)
        target.write_text(patched, encoding="utf-8")

        return f"Patched {rel_path}: replaced {count} occurrence(s)."

    def get_diff(self, file_path: str, old_content: str, new_content: str) -> str:
        """Generate a unified diff string."""
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3,
        )
        return "".join(diff)
