from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx
import structlog

from src.config import settings
from src.models import Metrics, ProcessedIdea
from src.utils.retry import async_retry

logger = structlog.get_logger(__name__)


class GitHubPublisher:
    """Publishes curated ideas to the GitHub repository.

    Handles:
    - Updating README.md with new ideas
    - Generating data/ideas.json for future web migration
    - Committing and pushing changes via GitHub API
    - Creating issues for alerts
    """

    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.github_token
        self.repo = settings.github_repo
        self.branch = settings.github_branch
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "open-source-radar/1.0",
                "Authorization": f"Bearer {self.token}",
            }
            self._client = httpx.AsyncClient(headers=headers, timeout=30.0)
        return self._client

    async def validate_config(self) -> bool:
        """Check that the GitHub token and repo are accessible."""
        if not self.token:
            logger.warning("github_publisher_no_token")
            return False
        try:
            client = await self._get_client()
            resp = await client.get(f"https://api.github.com/repos/{self.repo}")
            return resp.status_code == 200
        except Exception as e:
            logger.error("github_publisher_validation_error", error=str(e))
            return False

    @async_retry()
    async def publish_readme(self, content: str, commit_message: str = "docs: update README with new ideas") -> bool:
        """Update README.md in the repo via GitHub API."""
        if settings.dry_run:
            logger.info("dry_run_write_readme", size=len(content))
            return True

        client = await self._get_client()
        try:
            # Get current file SHA
            resp = await client.get(
                f"https://api.github.com/repos/{self.repo}/contents/README.md",
                params={"ref": self.branch},
            )

            sha = None
            if resp.status_code == 200:
                sha = resp.json().get("sha")

            # Update file
            put_resp = await client.put(
                f"https://api.github.com/repos/{self.repo}/contents/README.md",
                json={
                    "message": commit_message,
                    "content": self._encode_content(content),
                    "sha": sha,
                    "branch": self.branch,
                },
            )

            if put_resp.status_code in (200, 201):
                logger.info("readme_published")
                return True
            else:
                logger.error("readme_publish_failed", status=put_resp.status_code, body=put_resp.text[:500])
                return False

        except Exception as e:
            logger.error("readme_publish_error", error=str(e))
            return False

    @async_retry()
    async def publish_ideas_json(self, ideas: list[ProcessedIdea]) -> bool:
        """Generate and publish data/ideas.json for the future web platform."""
        json_entries = [idea.to_json_entry() for idea in ideas]

        # Also write locally
        ideas_json_path = settings.ideas_json_path
        ideas_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ideas_json_path, "w") as f:
            json.dump(json_entries, f, indent=2, default=str)

        if settings.dry_run:
            logger.info("dry_run_write_ideas_json", count=len(json_entries))
            return True

        client = await self._get_client()
        content = json.dumps(json_entries, indent=2, default=str)

        try:
            resp = await client.get(
                f"https://api.github.com/repos/{self.repo}/contents/data/ideas.json",
                params={"ref": self.branch},
            )

            sha = None
            if resp.status_code == 200:
                sha = resp.json().get("sha")

            put_resp = await client.put(
                f"https://api.github.com/repos/{self.repo}/contents/data/ideas.json",
                json={
                    "message": "chore: update ideas.json",
                    "content": self._encode_content(content),
                    "sha": sha,
                    "branch": self.branch,
                },
            )

            if put_resp.status_code in (200, 201):
                logger.info("ideas_json_published")
                return True
            else:
                logger.error("ideas_json_publish_failed", status=put_resp.status_code)
                return False

        except Exception as e:
            logger.error("ideas_json_publish_error", error=str(e))
            return False

    @async_retry()
    async def create_issue(self, title: str, body: str, labels: list[str] | None = None) -> str | None:
        """Create a GitHub issue for alerts."""
        if settings.dry_run:
            logger.info("dry_run_create_issue", title=title)
            return "dry-run-issue-id"

        client = await self._get_client()
        try:
            resp = await client.post(
                f"https://api.github.com/repos/{self.repo}/issues",
                json={
                    "title": title,
                    "body": body,
                    "labels": labels or ["alert"],
                },
            )

            if resp.status_code in (200, 201):
                issue_url = resp.json().get("html_url", "")
                logger.info("issue_created", url=issue_url)
                return issue_url
            else:
                logger.error("issue_create_failed", status=resp.status_code)
                return None

        except Exception as e:
            logger.error("issue_create_error", error=str(e))
            return None

    def write_ideas_json_local(self, ideas: list[ProcessedIdea]) -> None:
        """Write ideas.json locally (used for local development)."""
        json_entries = [idea.to_json_entry() for idea in ideas]
        ideas_json_path = settings.ideas_json_path
        ideas_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ideas_json_path, "w") as f:
            json.dump(json_entries, f, indent=2, default=str)
        logger.info("ideas_json_written_local", path=str(ideas_json_path), count=len(json_entries))

    def _encode_content(self, content: str) -> str:
        """Encode content to base64 for GitHub API."""
        import base64
        return base64.b64encode(content.encode()).decode()
