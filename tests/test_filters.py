from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.filters.deduplicator import Deduplicator
from src.filters.hard_rules import HardRulesFilter
from src.models import ApprovalStatus, RawIdea, SourceType


class TestHardRulesFilter:
    def test_approve_viral_github(self, sample_viral_github_idea):
        f = HardRulesFilter()
        status = f.evaluate(sample_viral_github_idea)
        assert status == ApprovalStatus.APPROVED

    def test_reject_low_score_github(self):
        from datetime import datetime
        idea = RawIdea(
            title="test",
            source=SourceType.GITHUB,
            source_id="1",
            stars=5,
            score=5,
            collected_at=datetime(2024, 1, 1),
        )
        f = HardRulesFilter()
        status = f.evaluate(idea)
        assert status == ApprovalStatus.REJECTED

    def test_pending_borderline_github(self, sample_raw_github_idea):
        f = HardRulesFilter()
        status = f.evaluate(sample_raw_github_idea)
        assert status == ApprovalStatus.PENDING

    def test_approve_viral_reddit(self):
        from datetime import datetime
        idea = RawIdea(
            title="viral post",
            source=SourceType.REDDIT,
            source_id="1",
            score=300,
            upvotes=300,
            collected_at=datetime(2024, 1, 1),
        )
        f = HardRulesFilter()
        status = f.evaluate(idea)
        assert status == ApprovalStatus.APPROVED

    def test_approve_viral_hackernews(self):
        from datetime import datetime
        idea = RawIdea(
            title="viral hn",
            source=SourceType.HACKER_NEWS,
            source_id="1",
            score=200,
            collected_at=datetime(2024, 1, 1),
        )
        f = HardRulesFilter()
        status = f.evaluate(idea)
        assert status == ApprovalStatus.APPROVED

    def test_quality_score_with_description(self, sample_raw_github_idea):
        f = HardRulesFilter()
        score = f.quality_score(sample_raw_github_idea)
        assert score > 0
        assert score <= 100

    def test_quality_score_minimal(self):
        from datetime import datetime
        idea = RawIdea(
            title="hi",
            source=SourceType.GITHUB,
            source_id="1",
            description="",
            score=0,
            stars=0,
            collected_at=datetime(2024, 1, 1),
        )
        f = HardRulesFilter()
        score = f.quality_score(idea)
        assert score < 20


@pytest.mark.asyncio
class TestDeduplicator:
    async def test_exact_title_match(self, db, sample_raw_github_idea):
        dedup = Deduplicator(db)
        # First time: not a duplicate
        assert await dedup.is_duplicate(sample_raw_github_idea) is False

        # Mark as processed
        from src.models import ProcessedIdea, ApprovalStatus
        processed = ProcessedIdea(
            id=sample_raw_github_idea.id,
            source=sample_raw_github_idea.source,
            source_id=sample_raw_github_idea.source_id,
            title=sample_raw_github_idea.title,
            description=sample_raw_github_idea.description,
            url=sample_raw_github_idea.url,
            author=sample_raw_github_idea.author,
            score=sample_raw_github_idea.score,
            stars=sample_raw_github_idea.stars,
            forks=sample_raw_github_idea.forks,
            language=sample_raw_github_idea.language,
            topics=sample_raw_github_idea.topics,
            comments=sample_raw_github_idea.comments,
            status=ApprovalStatus.APPROVED,
            discovered_at=sample_raw_github_idea.created_at or sample_raw_github_idea.collected_at,
            collected_at=sample_raw_github_idea.collected_at,
        )
        dedup.mark_as_processed(sample_raw_github_idea, processed)

        # Second time: should be detected as duplicate
        assert await dedup.is_duplicate(sample_raw_github_idea) is True

    async def test_url_match(self, db):
        from datetime import datetime
        dedup = Deduplicator(db)
        idea = RawIdea(
            title="test project",
            source=SourceType.GITHUB,
            source_id="url-test",
            url="https://github.com/test/project",
            score=50,
            collected_at=datetime(2024, 1, 1),
        )
        assert await dedup.is_duplicate(idea) is False

        # Same URL should be detected
        idea2 = RawIdea(
            title="test project 2",
            source=SourceType.GITHUB,
            source_id="url-test-2",
            url="https://github.com/test/project",
            score=50,
            collected_at=datetime(2024, 1, 1),
        )
        # Mark first one
        from src.models import ProcessedIdea, ApprovalStatus
        processed = ProcessedIdea(
            id=idea.id,
            source=idea.source,
            source_id=idea.source_id,
            title=idea.title,
            description=idea.description,
            url=idea.url,
            author=idea.author,
            score=idea.score,
            stars=idea.stars,
            forks=idea.forks,
            language=idea.language,
            topics=idea.topics,
            comments=idea.comments,
            status=ApprovalStatus.APPROVED,
            discovered_at=idea.created_at or idea.collected_at,
            collected_at=idea.collected_at,
        )
        dedup.mark_as_processed(idea, processed)

        assert await dedup.is_duplicate(idea2) is True

    def test_normalize_title(self, db):
        dedup = Deduplicator(db)
        assert dedup._normalize_title("  Hello World!  ") == "hello world"
        assert dedup._normalize_title("My Project (2024)") == "my project 2024"

    def test_fuzzy_key(self, db):
        dedup = Deduplicator(db)
        key = dedup._fuzzy_key("hello world")
        assert "hello" in key
        assert "world" in key


@pytest.mark.asyncio
async def test_ai_evaluator_basic(mock_ai_provider, sample_raw_github_idea):
    from src.filters.ai_evaluator import AIEvaluator

    evaluator = AIEvaluator(mock_ai_provider)
    status, verdict = await evaluator.evaluate(sample_raw_github_idea)

    assert status == ApprovalStatus.APPROVED
    assert verdict.approved is True
    assert verdict.confidence == 0.85
