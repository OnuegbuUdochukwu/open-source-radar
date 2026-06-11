"""Integration tests for the main pipeline orchestrator."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.main import OpenSourceRadar
from src.models import AIVerdict, DifficultyLevel, RawIdea, SourceType


@pytest.mark.asyncio
async def test_pipeline_dry_run(tmp_path, monkeypatch):
    """Test pipeline runs without errors in dry-run mode with in-memory database."""
    monkeypatch.setattr("src.config.settings.dry_run", True)
    monkeypatch.setattr("src.config.settings.database_path", ":memory:")

    with patch("src.main.GitHubPublisher") as mock_pub_cls, \
         patch("src.main.GeminiProvider") as mock_ai_cls:

        # Configure AI mock
        mock_ai = AsyncMock()
        mock_ai.provider_name = "test"
        mock_ai.evaluate_idea = AsyncMock(return_value=AIVerdict(
            approved=True,
            confidence=0.9,
            category="Web Development",
            difficulty=DifficultyLevel.INTERMEDIATE,
            summary="A web project",
            reasoning="Looks good",
        ))
        mock_ai_cls.return_value = mock_ai
        mock_ai.health_check = AsyncMock(return_value=True)

        # Configure publisher mock
        mock_pub = AsyncMock()
        mock_pub.publish_readme.return_value = True
        mock_pub.publish_ideas_json.return_value = True
        mock_pub_cls.return_value = mock_pub

        # Create radar instance with in-memory DB
        radar = OpenSourceRadar()
        radar.ai_evaluator.provider = mock_ai

        # Add a mock collector
        mock_collector = AsyncMock()
        mock_collector.source_name = "test"

        async def mock_collect():
            yield RawIdea(
                id="test-integration-1",
                source=SourceType.GITHUB,
                source_id="integration-1",
                title="Integration Test Project",
                description="A project for integration testing",
                url="https://github.com/test/integration",
                author="testuser",
                score=100,
                stars=100,
                forks=25,
                language="Python",
                topics=["testing"],
                comments=5,
                created_at=datetime(2024, 1, 1),
                collected_at=datetime(2024, 6, 15),
            )

        mock_collector.collect = mock_collect
        radar.collectors = [mock_collector]

        # Run pipeline
        results = await radar.run_daily_pipeline()

        assert results["collected"] >= 1
        assert results["published"] is True


@pytest.mark.asyncio
async def test_pipeline_with_multiple_ideas(db):
    """Test pipeline handles multiple ideas from multiple sources."""
    with patch("src.config.settings.dry_run", True):
        radar = OpenSourceRadar()
        radar.db = db

        # Create mock collectors
        mock_gh = AsyncMock()
        mock_gh.source_name = "github"

        async def collect_gh():
            for i in range(3):
                yield RawIdea(
                    id=f"gh-{i}",
                    source=SourceType.GITHUB,
                    source_id=f"gh-src-{i}",
                    title=f"GitHub Project {i}",
                    description=f"Description for project {i}",
                    url=f"https://github.com/test/proj-{i}",
                    author="testuser",
                    score=100,
                    stars=100,
                    forks=10,
                    language="Python",
                    topics=[],
                    comments=0,
                    created_at=datetime(2024, 1, 1),
                    collected_at=datetime(2024, 6, 15),
                )

        mock_gh.collect = collect_gh

        mock_reddit = AsyncMock()
        mock_reddit.source_name = "reddit"

        async def collect_reddit():
            yield RawIdea(
                id="reddit-1",
                source=SourceType.REDDIT,
                source_id="reddit-src-1",
                title="Reddit Project Idea",
                description="A great idea from Reddit",
                url="https://reddit.com/r/test",
                author="redditor",
                score=50,
                comments=10,
                created_at=datetime(2024, 1, 1),
                collected_at=datetime(2024, 6, 15),
            )

        mock_reddit.collect = collect_reddit

        radar.collectors = [mock_gh, mock_reddit]

        results = await radar.run_daily_pipeline()

        assert results["collected"] == 4
        assert results["published"] is True


@pytest.mark.asyncio
async def test_pipeline_handles_collector_failure(db):
    """Test pipeline continues when one collector fails."""
    with patch("src.config.settings.dry_run", True):
        radar = OpenSourceRadar()
        radar.db = db

        failing_collector = AsyncMock()
        failing_collector.source_name = "failing"

        async def fail_collect():
            raise ConnectionError("API unavailable")
            yield  # pragma: no cover

        failing_collector.collect = fail_collect

        working_collector = AsyncMock()
        working_collector.source_name = "working"

        async def work_collect():
            yield RawIdea(
                id="working-1",
                source=SourceType.GITHUB,
                source_id="working-src",
                title="Working Project",
                description="This collector works",
                url="https://github.com/test/working",
                author="test",
                score=50,
                stars=50,
                forks=5,
                language="Python",
                topics=[],
                comments=0,
                created_at=datetime(2024, 1, 1),
                collected_at=datetime(2024, 6, 15),
            )

        working_collector.collect = work_collect

        radar.collectors = [failing_collector, working_collector]

        results = await radar.run_daily_pipeline()

        # Should still collect from the working collector
        assert results["collected"] >= 1
        assert results["published"] is True
