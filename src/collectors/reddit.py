from __future__ import annotations

import time
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

REDDIT_SUBREDDITS = [
    "SideProject",
    "opensource",
    "coolgithubprojects",
    "webdev",
    "programming",
    "learnprogramming",
    "reactjs",
    "Python",
]


class RedditCollector(BaseCollector):
    """Collects project ideas from Reddit subreddits.

    Uses the public JSON endpoint to avoid requiring API credentials
    for basic scraping. Falls back to OAuth if credentials are provided.
    """

    source_name = "reddit"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.client_id = client_id or settings.reddit_client_id
        self.client_secret = client_secret or settings.reddit_client_secret
        self.user_agent = user_agent or settings.reddit_user_agent
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"User-Agent": self.user_agent}
            self._client = httpx.AsyncClient(headers=headers, timeout=30.0)
            if self.client_id and self.client_secret:
                await self._authenticate()
        return self._client

    async def _authenticate(self) -> None:
        try:
            auth = httpx.BasicAuth(self.client_id, self.client_secret)
            resp = await self._client.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data={"grant_type": "client_credentials"},
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token", "")
                self._client.headers["Authorization"] = f"Bearer {self._access_token}"
                logger.info("reddit_authenticated")
            else:
                logger.warning("reddit_auth_failed", status=resp.status_code)
        except Exception as e:
            logger.warning("reddit_auth_error", error=str(e))

    async def validate_source(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("https://www.reddit.com/api/v1/me" if self._access_token else "https://www.reddit.com/r/all/about.json")
            return resp.status_code in (200, 401)
        except Exception as e:
            logger.warning("reddit_validation_failed", error=str(e))
            return False

    @async_retry()
    async def collect(self) -> AsyncIterator[RawIdea]:
        client = await self._get_client()

        for subreddit in REDDIT_SUBREDDITS:
            logger.info("reddit_collecting", subreddit=subreddit)
            after = None
            fetched = 0

            while fetched < settings.max_ideas_per_source:
                url = f"https://www.reddit.com/r/{subreddit}/hot.json"
                params: dict[str, Any] = {"limit": 25}
                if after:
                    params["after"] = after

                try:
                    resp = await client.get(url, params=params)

                    if resp.status_code == 429:
                        logger.warning("reddit_rate_limited", subreddit=subreddit)
                        time.sleep(60)
                        continue
                    if resp.status_code != 200:
                        logger.warning("reddit_error", subreddit=subreddit, status=resp.status_code)
                        break

                    data = resp.json()
                    children = data.get("data", {}).get("children", [])

                    if not children:
                        break

                    for child in children:
                        post = child.get("data", {})
                        idea = self._post_to_idea(post, subreddit)
                        if idea:
                            yield idea
                            fetched += 1
                            if fetched >= settings.max_ideas_per_source:
                                break

                    after = data.get("data", {}).get("after")
                    if not after:
                        break

                except httpx.TimeoutException:
                    logger.warning("reddit_timeout", subreddit=subreddit)
                    break
                except Exception as e:
                    logger.error("reddit_collect_error", subreddit=subreddit, error=str(e))
                    break

    def _post_to_idea(self, post: dict[str, Any], subreddit: str) -> RawIdea | None:
        try:
            title = post.get("title", "")
            if not title:
                return None

            created_utc = post.get("created_utc")
            created_at = datetime.utcfromtimestamp(created_utc) if created_utc else None

            return RawIdea(
                source=SourceType.REDDIT,
                source_id=post.get("id", ""),
                title=title,
                description=post.get("selftext", "") or "",
                url=f"https://reddit.com{post.get('permalink', '')}",
                author=post.get("author", ""),
                score=post.get("ups", 0) or 0,
                upvotes=post.get("ups", 0) or 0,
                comments=post.get("num_comments", 0) or 0,
                created_at=created_at,
                raw_data={
                    "subreddit": subreddit,
                    "domain": post.get("domain", ""),
                    "over_18": post.get("over_18", False),
                    "is_self": post.get("is_self", True),
                    "score": post.get("score", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0),
                },
            )
        except Exception as e:
            logger.error("reddit_post_parse_error", error=str(e))
            return None
