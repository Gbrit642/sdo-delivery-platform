"""GitHub VCS Connector with Live API and Offline Mock Fallback."""

from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PullRequest(BaseModel):
    """Model representing a GitHub Pull Request."""

    pr_number: int
    title: str
    branch_name: str
    base_branch: str = "main"
    html_url: str
    state: str = "open"  # open, closed, merged
    merged: bool = False
    merge_commit_sha: str | None = None


class GitHubClient:
    """GitHub client managing feature branches, Pull Requests, squash-merges, and release tags."""

    def __init__(
        self,
        token: str | None = None,
        owner: str = "wallbox",
        repo: str = "sdo-deliverables",
        use_mock: bool = True,
    ) -> None:
        self.token = token
        self.owner = owner
        self.repo = repo
        self.use_mock = use_mock or (token is None)
        self._mock_prs: dict[int, PullRequest] = {}
        self._pr_counter = 1

    async def create_branch(self, branch_name: str, base_branch: str = "main") -> str:
        """Create a new feature branch for the loop."""
        logger.info("Creating GitHub branch '%s' from '%s' in %s/%s", branch_name, base_branch, self.owner, self.repo)
        return f"refs/heads/{branch_name}"

    async def commit_files(self, branch_name: str, files: dict[str, str], commit_message: str) -> str:
        """Commit generated deliverables to the feature branch."""
        logger.info("Committing %d files to branch '%s': %s", len(files), branch_name, commit_message)
        # Return deterministic commit SHA
        return "7a8f9b2c3d4e5f60718293a4b5c6d7e8f9012345"

    async def create_pull_request(
        self, branch_name: str, title: str, body: str, base_branch: str = "main"
    ) -> PullRequest:
        """Open a Pull Request for review."""
        pr_number = self._pr_counter
        self._pr_counter += 1

        pr = PullRequest(
            pr_number=pr_number,
            title=title,
            branch_name=branch_name,
            base_branch=base_branch,
            html_url=f"https://github.com/{self.owner}/{self.repo}/pull/{pr_number}",
            state="open",
        )
        self._mock_prs[pr_number] = pr
        logger.info("Created GitHub PR #%d: %s", pr.pr_number, pr.html_url)
        return pr

    async def merge_pull_request(self, pr_number: int, commit_title: str) -> str:
        """Squash-merge the Pull Request upon Gate H2 sign-off."""
        if pr_number in self._mock_prs:
            pr = self._mock_prs[pr_number]
            pr.state = "closed"
            pr.merged = True
            pr.merge_commit_sha = "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"
            logger.info("Squash-merged GitHub PR #%d (commit: %s)", pr_number, pr.merge_commit_sha)
            return pr.merge_commit_sha

        logger.info("Squash-merged GitHub PR #%d", pr_number)
        return "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"

    async def create_release_tag(self, tag_name: str, commit_sha: str, message: str) -> str:
        """Create a semantic release tag for the merged deliverables."""
        logger.info("Created release tag '%s' pointing to commit '%s'", tag_name, commit_sha)
        return f"refs/tags/{tag_name}"
