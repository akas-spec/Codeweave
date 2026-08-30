import os
import shutil
import logging
from pathlib import Path
from typing import Optional
import httpx
from git import Repo as GitRepo
from app.config import settings

logger = logging.getLogger(__name__)


class GitHubService:
    """Service for GitHub operations: cloning repos, fetching info, creating PRs."""

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self.repos_dir = Path(settings.REPOS_DIR)
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    async def get_repo_info(self, owner: str, repo: str) -> dict:
        """Fetch repository information from GitHub API."""
        async with httpx.AsyncClient() as client:
            headers = {"Accept": "application/json"}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_user_repos(self) -> list[dict]:
        """Fetch all repositories for the authenticated user."""
        if not self.access_token:
            raise ValueError("Access token is required to fetch user repositories")
            
        async with httpx.AsyncClient() as client:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = await client.get(
                "https://api.github.com/user/repos?sort=updated&per_page=100",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def clone_repo(self, github_url: str, repo_full_name: str) -> Path:
        """Clone a GitHub repository to local disk.
        
        Returns the path to the cloned repository.
        """
        # Create safe directory name
        safe_name = repo_full_name.replace("/", "_")
        clone_path = self.repos_dir / safe_name

        # Remove existing clone if present
        if clone_path.exists():
            import stat
            def remove_readonly(func, path, _):
                os.chmod(path, stat.S_IWRITE)
                try:
                    func(path)
                except Exception:
                    pass
            shutil.rmtree(clone_path, onerror=remove_readonly)

        logger.info(f"Cloning {github_url} to {clone_path}")

        # Clone with token if available (for private repos)
        clone_url = github_url
        if self.access_token and "github.com" in github_url:
            # Insert token into URL for auth
            clone_url = github_url.replace(
                "https://github.com",
                f"https://x-access-token:{self.access_token}@github.com"
            )

        GitRepo.clone_from(clone_url, str(clone_path), depth=1)  # Shallow clone
        logger.info(f"Successfully cloned {repo_full_name}")
        return clone_path

    def get_clone_path(self, repo_full_name: str) -> Path:
        """Get the local path for a cloned repository."""
        safe_name = repo_full_name.replace("/", "_")
        return self.repos_dir / safe_name

    @staticmethod
    def parse_github_url(url: str) -> tuple[str, str]:
        """Parse a GitHub URL into (owner, repo) tuple.
        
        Supports:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - github.com/owner/repo
        """
        url = url.rstrip("/").removesuffix(".git")
        parts = url.split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub URL: {url}")
        return parts[-2], parts[-1]
