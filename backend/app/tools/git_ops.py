import logging
import asyncio
from pathlib import Path
from typing import Optional
import httpx
from git import Repo as GitRepo

logger = logging.getLogger(__name__)


class GitOpsTool:
    """Tool: perform Git operations — branch, commit, push, create PR.
    
    Uses GitPython for local git operations and GitHub REST API for PRs.
    """
    name = "git_ops"
    description = "Perform git operations: create branch, commit changes, push, or create a pull request."
    parameters = {
        "action": {"type": "string", "description": "'create_branch', 'commit', 'push', or 'create_pr'"},
        "branch_name": {"type": "string", "description": "Branch name (for create_branch/push/create_pr)"},
        "message": {"type": "string", "description": "Commit message (for commit) or PR title (for create_pr)"},
        "body": {"type": "string", "description": "PR body/description (for create_pr only)"},
        "base_branch": {"type": "string", "description": "Base branch for PR (default: main)"},
    }

    def __init__(
        self,
        repo_path: Path,
        github_token: Optional[str] = None,
        repo_full_name: Optional[str] = None,
    ):
        self._repo_path = repo_path
        self._github_token = github_token
        self._repo_full_name = repo_full_name  # e.g. "owner/repo"

    async def execute(
        self,
        action: str,
        branch_name: Optional[str] = None,
        message: Optional[str] = None,
        body: Optional[str] = None,
        base_branch: str = "main",
    ) -> str:
        """Execute a git operation."""
        try:
            if action == "create_branch":
                return await self._create_branch(branch_name)
            elif action == "commit":
                return await self._commit(message)
            elif action == "push":
                return await self._push(branch_name)
            elif action == "create_pr":
                return await self._create_pr(branch_name, message, body, base_branch)
            else:
                return f"Unknown git action: {action}. Use: create_branch, commit, push, create_pr"
        except Exception as e:
            logger.error("GitOpsTool error (%s): %s", action, e)
            return f"Git operation '{action}' failed: {e}"

    async def _create_branch(self, branch_name: Optional[str]) -> str:
        """Create and checkout a new branch."""
        if not branch_name:
            return "Error: branch_name is required"

        def _do():
            repo = GitRepo(str(self._repo_path))
            # Check if branch already exists
            if branch_name in [b.name for b in repo.branches]:
                repo.git.checkout(branch_name)
                return f"Branch '{branch_name}' already exists. Checked out."
            # Create from current HEAD
            repo.git.checkout("-b", branch_name)
            return f"Created and checked out branch: {branch_name}"

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do)

    async def _commit(self, message: Optional[str]) -> str:
        """Stage all changes and commit."""
        if not message:
            return "Error: commit message is required"

        def _do():
            repo = GitRepo(str(self._repo_path))
            # Stage all changes
            repo.git.add("--all")
            # Check if there are staged changes
            if not repo.index.diff("HEAD") and not repo.untracked_files:
                return "Nothing to commit — working tree clean."
            repo.index.commit(message)
            return f"Committed: {message}"

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do)

    async def _push(self, branch_name: Optional[str]) -> str:
        """Push branch to origin."""
        if not branch_name:
            return "Error: branch_name is required for push"

        def _do():
            try:
                repo = GitRepo(str(self._repo_path))
                origin = repo.remote("origin")
                push_info = origin.push(branch_name)
                if push_info and push_info[0].flags & push_info[0].ERROR:
                    return f"Push failed: {push_info[0].summary}"
                return f"Pushed branch '{branch_name}' to origin."
            except Exception as e:
                if "403" in str(e):
                    return "Error: GitHub 403 Forbidden. You do not have push access to this repository. Do not retry pushing. Call 'done' to finish."
                raise

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do)

    async def _create_pr(
        self,
        branch_name: Optional[str],
        title: Optional[str],
        body: Optional[str],
        base_branch: str,
    ) -> str:
        """Create a Pull Request via GitHub REST API."""
        if not branch_name or not title:
            return "Error: branch_name and message (title) are required for create_pr"
        if not self._github_token:
            return "Error: GitHub token not available. Cannot create PR."
        if not self._repo_full_name:
            return "Error: Repository full name (owner/repo) not set."

        # 1-second delay to respect GitHub secondary rate limits
        await asyncio.sleep(1)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api.github.com/repos/{self._repo_full_name}/pulls",
                json={
                    "title": title,
                    "head": branch_name,
                    "base": base_branch,
                    "body": body or f"Automated fix by CodeWeave\n\n{title}",
                },
                headers={
                    "Authorization": f"Bearer {self._github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

            if response.status_code == 201:
                pr_data = response.json()
                return f"PR created: {pr_data['html_url']}"
            elif response.status_code == 422:
                detail = response.json().get("errors", [{}])
                return f"PR creation failed (422): {detail}"
            else:
                return f"PR creation failed ({response.status_code}): {response.text[:500]}"
