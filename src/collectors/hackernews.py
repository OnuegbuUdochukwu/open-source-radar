from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator

import httpx
import structlog

from src.collectors.base import BaseCollector
from src.config import settings
from src.models import RawIdea, SourceType
from src.utils.retry import async_retry

logger = structlog.get_logger(__name__)

HN_SEARCH_TAGS = [
    "project",
    "open-source",
    "side-project",
    "show-hn",
    "build",
    "tool",
    "library",
    "framework",
]


class HackerNewsCollector(BaseCollector):
    """Collects project ideas from Hacker News.

    Uses the official Firebase API for item data and Algolia search
    for discovery. Two-phase: search for relevant stories then fetch details.
    """

    source_name = "hackernews"
    _api_base = "https://hacker-news.firebaseio.com/v0"
    _algolia_base = "https://hn.algolia.com/api/v1"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def validate_source(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(f"{self._api_base}/maxitem.json")
            return resp.status_code == 200
        except Exception as e:
            logger.warning("hn_validation_failed", error=str(e))
            return False

    @async_retry()
    async def collect(self) -> AsyncIterator[RawIdea]:
        client = await self._get_client()
        seen_ids: set[int] = set()

        for tag in HN_SEARCH_TAGS:
            logger.info("hn_search", tag=tag)
            page = 0

            while page < 5:
                try:
                    resp = await client.get(
                        f"{self._algolia_base}/search",
                        params={
                            "query": tag,
                            "tags": "story",
                            "hitsPerPage": 50,
                            "page": page,
                        },
                    )

                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    hits = data.get("hits", [])

                    if not hits:
                        break

                    for hit in hits:
                        object_id = hit.get("objectID")
                        if not object_id or int(object_id) in seen_ids:
                            continue

                        seen_ids.add(int(object_id))
                        idea = self._hit_to_idea(hit, tag)
                        if idea:
                            yield idea

                    page += 1

                except httpx.TimeoutException:
                    logger.warning("hn_algolia_timeout", tag=tag)
                    break
                except Exception as e:
                    logger.error("hn_algolia_error", tag=tag, error=str(e))
                    break

        # Also fetch top stories directly
        try:
            resp = await client.get(f"{self._api_base}/topstories.json")
            if resp.status_code == 200:
                top_ids = resp.json()[:50]
                for story_id in top_ids:
                    if story_id in seen_ids:
                        continue
                    seen_ids.add(story_id)
                    try:
                        story_resp = await client.get(
                            f"{self._api_base}/item/{story_id}.json"
                        )
                        if story_resp.status_code == 200:
                            story = story_resp.json()
                            if story and story.get("type") == "story" and story.get("title"):
                                idea = self._story_to_idea(story)
                                if idea:
                                    yield idea
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("hn_top_stories_error", error=str(e))

    def _hit_to_idea(self, hit: dict[str, Any], tag: str) -> RawIdea | None:
        try:
            title = hit.get("title", "")
            if not title:
                return None

            created_at = hit.get("created_at")
            parsed_date = (
                datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if created_at else None
            )

            return RawIdea(
                source=SourceType.HACKER_NEWS,
                source_id=str(hit.get("objectID", "")),
                title=title,
                description=hit.get("story_text", "") or hit.get("comment_text", "") or "",
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                author=hit.get("author", ""),
                score=hit.get("points", 0) or 0,
                comments=hit.get("num_comments", 0) or 0,
                created_at=parsed_date,
                raw_data={
                    "search_tag": tag,
                    "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                },
            )
        except Exception as e:
            logger.error("hn_hit_parse_error", error=str(e))
            return None

    def _story_to_idea(self, story: dict[str, Any]) -> RawIdea | None:
        try:
            title = story.get("title", "")
            if not title:
                return None

            time_val = story.get("time")
            created_at = datetime.utcfromtimestamp(time_val) if time_val else None

            return RawIdea(
                source=SourceType.HACKER_NEWS,
                source_id=str(story.get("id", "")),
                title=title,
                description=story.get("text", "") or "",
                url=story.get("url") or f"https://news.ycombinator.com/item?id={story.get('id', '')}",
                author=story.get("by", ""),
                score=story.get("score", 0) or 0,
                comments=story.get("descendants", 0) or 0,
                created_at=created_at,
                raw_data={
                    "type": story.get("type", ""),
                    "hn_url": f"https://news.ycombinator.com/item?id={story.get('id', '')}",
                },
            )
        except Exception as e:
            logger.error("hn_story_parse_error", error=str(e))
            return None
