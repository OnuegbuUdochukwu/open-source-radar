from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx
import structlog

from src.collectors.base import BaseCollector
from src.config import settings
from src.models import RawIdea, SourceType
from src.utils.retry import async_retry

logger = structlog.get_logger(__name__)

GITHUB_SEARCH_QUERIES = [
    "project-ideas",
    "side-project",
    "open-source",
    "beginner-project",
    "good-first-issue",
    "hackathon-project",
    "portfolio-project",
    "learning-project",
    "starter-project",
    "build-tool",
]


class GitHubCollector(BaseCollector):
    """Collects project ideas from GitHub search results."""

    source_name = "github"
    _base_url = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.github_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "open-source-radar/1.0",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def validate_source(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("/")
            return resp.status_code == 200
        except Exception as e:
            logger.warning("github_validation_failed", error=str(e))
            return False

    @async_retry()
    async def collect(self) -> AsyncIterator[RawIdea]:
        client = await self._get_client()

        for query in GITHUB_SEARCH_QUERIES:
            logger.info("github_search", query=query)
            page = 1
            fetched = 0

            while fetched < settings.max_ideas_per_source:
                try:
                    resp = await client.get(
                        "/search/repositories",
                        params={
                            "q": query,
                            "sort": "stars",
                            "order": "desc",
                            "per_page": min(30, settings.max_ideas_per_source - fetched),
                            "page": page,
                        },
                    )

                    if resp.status_code == 403:
                        logger.warning("github_rate_limited", query=query)
                        break
                    if resp.status_code != 200:
                        logger.error("github_search_error", query=query, status=resp.status_code)
                        break

                    data = resp.json()
                    items = data.get("items", [])

                    if not items:
                        break

                    for repo in items:
                        idea = self._repo_to_idea(repo, query)
                        if idea:
                            yield idea
                            fetched += 1

                    page += 1
                    if page > 10:
                        break

                except httpx.TimeoutException:
                    logger.warning("github_timeout", query=query)
                    break
                except Exception as e:
                    logger.error("github_collect_error", query=query, error=str(e))
                    break

        if self._client:
            await self._client.aclose()
            self._client = None

    def _repo_to_idea(self, repo: dict[str, Any], search_query: str) -> RawIdea | None:
        try:
            name = repo.get("full_name", "") or repo.get("name", "")
            if not name:
                return None

            description = repo.get("description", "") or ""
            topics = repo.get("topics", []) or []
            language = repo.get("language", "") or ""
            stars = repo.get("stargazers_count", 0) or 0
            forks = repo.get("forks_count", 0) or 0

            created_str = repo.get("created_at")
            updated_str = repo.get("updated_at")
            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else None
            updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00")) if updated_str else None

            return RawIdea(
                source=SourceType.GITHUB,
                source_id=str(repo.get("id", "")),
                title=name,
                description=description,
                url=repo.get("html_url", ""),
                author=(repo.get("owner") or {}).get("login", ""),
                stars=stars,
                forks=forks,
                language=language,
                topics=topics,
                score=stars,
                created_at=created_at,
                updated_at=updated_at,
                raw_data={
                    "search_query": search_query,
                    "full_name": name,
                    "default_branch": repo.get("default_branch", ""),
                    "open_issues": repo.get("open_issues_count", 0),
                    "license": (repo.get("license") or {}).get("spdx_id") if repo.get("license") else None,
                },
            )
        except Exception as e:
            logger.error("github_repo_parse_error", error=str(e))
            return None
