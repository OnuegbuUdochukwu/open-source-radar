from __future__ import annotations

from datetime import datetime

from src.models import (
    ApprovalStatus,
    DifficultyLevel,
    ProcessedIdea,
    RawIdea,
    SourceType,
)


class TestRawIdea:
    def test_default_fields(self):
        from datetime import datetime
        idea = RawIdea(
            title="Test",
            source=SourceType.GITHUB,
            source_id="1",
            score=50,
            collected_at=datetime(2024, 1, 1),
        )
        assert idea.id is not None
        assert idea.topics == []
        assert idea.collected_at is not None

    def test_with_all_fields(self):
        idea = RawIdea(
            id="custom-id",
            source=SourceType.REDDIT,
            source_id="reddit-123",
            title="Reddit Post",
            description="A Reddit post description",
            url="https://reddit.com/r/test",
            author="user123",
            score=100,
            upvotes=100,
            stars=0,
            forks=0,
            language="",
            topics=["python", "tool"],
            comments=25,
            created_at=datetime(2024, 1, 1),
            updated_at=None,
            collected_at=datetime(2024, 6, 15),
            raw_data={"source_url": "https://reddit.com"},
        )
        assert idea.id == "custom-id"
        assert idea.source == SourceType.REDDIT
        assert "python" in idea.topics

    def test_minimal_idea(self):
        from datetime import datetime
        idea = RawIdea(
            title="Minimal",
            source=SourceType.HACKER_NEWS,
            source_id="hn-1",
            score=10,
            collected_at=datetime(2024, 1, 1),
        )
        assert idea.description == ""
        assert idea.url == ""


class TestProcessedIdea:
    def test_default_status(self):
        idea = ProcessedIdea(
            id="1",
            source=SourceType.GITHUB,
            source_id="1",
            title="Test",
            description="",
            url="",
            author="",
            score=0,
            stars=0,
            forks=0,
            language="",
            topics=[],
            comments=0,
            discovered_at=datetime(2024, 1, 1),
            collected_at=datetime(2024, 6, 15),
        )
        assert idea.status == ApprovalStatus.PENDING

    def test_to_json_entry(self):
        idea = ProcessedIdea(
            id="json-1",
            source=SourceType.GITHUB,
            source_id="gh-1",
            title="JSON Test",
            description="Testing JSON output",
            url="https://github.com/test/json-test",
            author="testuser",
            score=100,
            stars=100,
            forks=25,
            language="Python",
            topics=["json", "test"],
            comments=5,
            categories=["Python", "Developer Tools"],
            difficulty=DifficultyLevel.INTERMEDIATE,
            tech_stack=["Python", "JSON"],
            status=ApprovalStatus.APPROVED,
            ai_confidence=0.95,
            quality_score=80.0,
            discovered_at=datetime(2024, 1, 1),
            collected_at=datetime(2024, 6, 15),
        )

        entry = idea.to_json_entry()
        assert entry["id"] == "json-1"
        assert entry["title"] == "JSON Test"
        assert "Python" in entry["category"]
        assert entry["source"] == "github"
        assert entry["language"] == "Python"
        assert entry["stars"] == 100
        assert entry["score"] == 100


def test_category_enum_values():
    assert DifficultyLevel.BEGINNER.value == "Beginner"
    assert DifficultyLevel.INTERMEDIATE.value == "Intermediate"
    assert DifficultyLevel.ADVANCED.value == "Advanced"


def test_status_enum_values():
    assert ApprovalStatus.PENDING.value == "pending"
    assert ApprovalStatus.APPROVED.value == "approved"
    assert ApprovalStatus.REJECTED.value == "rejected"
    assert ApprovalStatus.DUPLICATE.value == "duplicate"


def test_source_enum_values():
    assert SourceType.GITHUB.value == "github"
    assert SourceType.REDDIT.value == "reddit"
    assert SourceType.HACKER_NEWS.value == "hackernews"
