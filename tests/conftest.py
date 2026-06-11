from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.config import Settings
from src.database import Database
from src.models import (
    ApprovalStatus,
    DifficultyLevel,
    ProcessedIdea,
    RawIdea,
    SourceType,
)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        gemini_api_key="test-key",
        ai_evaluation_enabled=False,
        database_path=":memory:",
        dry_run=True,
        github_stars_viral=500,
        github_stars_minimum=20,
        reddit_upvotes_viral=200,
        reddit_upvotes_minimum=10,
        hackernews_score_viral=150,
        hackernews_score_minimum=15,
    )


@pytest.fixture
def db() -> Database:
    _db = Database(":memory:")
    _db.initialize()
    return _db


@pytest.fixture
def sample_raw_github_idea() -> RawIdea:
    return RawIdea(
        id="test-gh-1",
        source=SourceType.GITHUB,
        source_id="12345",
        title="awesome-project",
        description="A revolutionary open-source project that solves world hunger using AI",
        url="https://github.com/testuser/awesome-project",
        author="testuser",
        score=100,
        stars=100,
        forks=25,
        language="Python",
        topics=["ai", "machine-learning", "open-source"],
        comments=0,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 6, 1),
        collected_at=datetime(2024, 6, 15),
    )


@pytest.fixture
def sample_raw_reddit_idea() -> RawIdea:
    return RawIdea(
        id="test-reddit-1",
        source=SourceType.REDDIT,
        source_id="abc123",
        title="I built a CLI tool for managing Docker containers",
        description="After months of work, I finally released my CLI tool...",
        url="https://reddit.com/r/opensource/comments/abc123",
        author="devuser",
        score=50,
        comments=12,
        created_at=datetime(2024, 6, 10),
        collected_at=datetime(2024, 6, 15),
    )


@pytest.fixture
def sample_viral_github_idea() -> RawIdea:
    return RawIdea(
        id="test-viral-gh",
        source=SourceType.GITHUB,
        source_id="99999",
        title="super-popular-framework",
        description="A web framework used by millions",
        url="https://github.com/bigtech/super-popular-framework",
        author="bigtech",
        score=5000,
        stars=5000,
        forks=1200,
        language="TypeScript",
        topics=["web", "framework", "typescript"],
        collected_at=datetime(2024, 6, 15),
    )


@pytest.fixture
def sample_processed_idea() -> ProcessedIdea:
    return ProcessedIdea(
        id="processed-1",
        source=SourceType.GITHUB,
        source_id="12345",
        title="awesome-project",
        description="A revolutionary open-source project",
        url="https://github.com/testuser/awesome-project",
        author="testuser",
        score=100,
        stars=100,
        forks=25,
        language="Python",
        topics=["ai", "machine-learning"],
        comments=0,
        categories=["AI/ML", "Python"],
        difficulty=DifficultyLevel.INTERMEDIATE,
        tech_stack=["Python", "AI"],
        status=ApprovalStatus.APPROVED,
        ai_confidence=0.92,
        ai_reasoning="Legitimate project with clear purpose",
        quality_score=75.0,
        fingerprint="test-fingerprint",
        discovered_at=datetime(2024, 1, 1),
        collected_at=datetime(2024, 6, 15),
        approved_at=datetime(2024, 6, 15),
    )


@pytest.fixture
def mock_ai_provider() -> AsyncMock:
    from src.models import AIVerdict

    provider = AsyncMock()
    provider.provider_name = "test"
    provider.evaluate_idea.return_value = AIVerdict(
        approved=True,
        confidence=0.85,
        category="Web Development",
        difficulty=DifficultyLevel.INTERMEDIATE,
        summary="A web development project",
        reasoning="Legitimate project",
    )
    provider.health_check.return_value = True
    return provider
