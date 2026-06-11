from __future__ import annotations

import pytest

from src.filters.ai_evaluator import AIEvaluator
from src.models import ApprovalStatus


@pytest.mark.asyncio
async def test_evaluate_approved(mock_ai_provider, sample_raw_github_idea):
    evaluator = AIEvaluator(mock_ai_provider)
    status, verdict = await evaluator.evaluate(sample_raw_github_idea)
    assert status == ApprovalStatus.APPROVED
    assert verdict.approved is True
    assert verdict.confidence > 0.5


@pytest.mark.asyncio
async def test_evaluate_rejected(mock_ai_provider, sample_raw_github_idea):
    from src.models import AIVerdict

    mock_ai_provider.evaluate_idea.return_value = AIVerdict(
        approved=False,
        confidence=0.2,
        category="Other",
        difficulty="Beginner",
        summary="Not useful",
        reasoning="Spam detected",
    )

    evaluator = AIEvaluator(mock_ai_provider)
    status, verdict = await evaluator.evaluate(sample_raw_github_idea)
    assert status == ApprovalStatus.REJECTED
    assert verdict.approved is False


@pytest.mark.asyncio
async def test_enrich_idea(mock_ai_provider, sample_raw_github_idea):
    from src.models import AIVerdict, DifficultyLevel

    evaluator = AIEvaluator(mock_ai_provider)
    verdict = AIVerdict(
        approved=True,
        confidence=0.9,
        category="Web Development",
        difficulty=DifficultyLevel.ADVANCED,
        summary="Build a web app",
        reasoning="Great project for learning",
    )

    processed = evaluator.enrich_idea(
        sample_raw_github_idea,
        verdict,
        ApprovalStatus.APPROVED,
        quality_score=85.0,
    )

    assert processed.status == ApprovalStatus.APPROVED
    assert processed.ai_confidence == 0.9
    assert "Web Development" in processed.categories
    assert processed.difficulty == DifficultyLevel.ADVANCED
    assert processed.quality_score == 85.0
    assert processed.ai_reasoning == "Great project for learning"


@pytest.mark.asyncio
async def test_ai_evaluator_disabled(mock_ai_provider, sample_raw_github_idea):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.config.settings.ai_evaluation_enabled", False)
        evaluator = AIEvaluator(mock_ai_provider)
        status, verdict = await evaluator.evaluate(sample_raw_github_idea)
        assert status == ApprovalStatus.PENDING
        assert verdict.approved is False
