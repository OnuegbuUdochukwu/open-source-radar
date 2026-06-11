from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.collectors.github import GitHubCollector
from src.collectors.reddit import RedditCollector
from src.collectors.hackernews import HackerNewsCollector


@pytest.mark.asyncio
async def test_github_collector_validate():
    collector = GitHubCollector()
    mock_client = AsyncMock()
    resp = AsyncMock()
    resp.status_code = 200
    mock_client.get.return_value = resp
    collector._get_client = AsyncMock(return_value=mock_client)
    result = await collector.validate_source()
    assert result is True


@pytest.mark.asyncio
async def test_github_collector_parse_repo():
    collector = GitHubCollector()
    sample_repo = {
        "id": 12345,
        "full_name": "testuser/awesome-project",
        "name": "awesome-project",
        "description": "An awesome open-source project",
        "html_url": "https://github.com/testuser/awesome-project",
        "owner": {"login": "testuser"},
        "stargazers_count": 100,
        "forks_count": 25,
        "language": "Python",
        "topics": ["ai", "machine-learning"],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-06-01T00:00:00Z",
        "open_issues_count": 5,
        "default_branch": "main",
        "license": {"spdx_id": "MIT"},
    }
    idea = collector._repo_to_idea(sample_repo, "project-ideas")
    assert idea is not None
    assert idea.title == "testuser/awesome-project"
    assert idea.stars == 100
    assert idea.language == "Python"
    assert idea.source_id == "12345"


@pytest.mark.asyncio
async def test_reddit_collector_parse_post():
    collector = RedditCollector()
    sample_post = {
        "id": "abc123",
        "title": "I built a CLI tool for managing Docker containers",
        "selftext": "After months of work...",
        "permalink": "/r/opensource/comments/abc123/",
        "author": "devuser",
        "ups": 50,
        "num_comments": 12,
        "created_utc": 1718000000,
        "domain": "self.opensource",
        "over_18": False,
        "is_self": True,
        "score": 50,
        "upvote_ratio": 0.85,
    }
    idea = collector._post_to_idea(sample_post, "opensource")
    assert idea is not None
    assert idea.title == "I built a CLI tool for managing Docker containers"
    assert idea.score == 50
    assert "reddit.com" in idea.url


@pytest.mark.asyncio
async def test_hackernews_collector_parse_hit():
    collector = HackerNewsCollector()
    sample_hit = {
        "objectID": "98765",
        "title": "Show HN: A new open-source database",
        "url": "https://example.com/db",
        "author": "hacker123",
        "points": 75,
        "num_comments": 20,
        "created_at": "2024-06-10T12:00:00Z",
        "story_text": "I built a new database from scratch...",
    }
    idea = collector._hit_to_idea(sample_hit, "project")
    assert idea is not None
    assert idea.title == "Show HN: A new open-source database"
    assert idea.score == 75


@pytest.mark.asyncio
async def test_github_collector_skip_empty():
    collector = GitHubCollector()
    idea = collector._repo_to_idea({}, "test")
    assert idea is None


@pytest.mark.asyncio
async def test_reddit_collector_skip_no_title():
    collector = RedditCollector()
    idea = collector._post_to_idea({"id": "test"}, "test")
    assert idea is None


@pytest.mark.asyncio
async def test_hackernews_collector_skip_no_title():
    collector = HackerNewsCollector()
    idea = collector._hit_to_idea({"objectID": "1"}, "test")
    assert idea is None
