from __future__ import annotations

import structlog

from src.ai.base import AIProvider
from src.config import settings
from src.models import ApprovalStatus, AIVerdict, ProcessedIdea, RawIdea
from src.utils.retry import async_retry

logger = structlog.get_logger(__name__)


class AIEvaluator:
    """Layer 2: AI-powered evaluation for borderline ideas.

    Receives ideas that passed Layer 1 with PENDING status and
    uses the configured AI provider to make a decision.
    """

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    @async_retry()
    async def evaluate(self, idea: RawIdea) -> tuple[ApprovalStatus, AIVerdict]:
        """Evaluate a single idea using AI.

        Returns:
            Tuple of (status, verdict)
        """
        if not settings.ai_evaluation_enabled:
            logger.info("ai_evaluation_disabled", title=idea.title)
            return ApprovalStatus.PENDING, AIVerdict(
                approved=False,
                confidence=0.0,
                category="Other",
                reasoning="AI evaluation disabled",
            )

        logger.info("ai_evaluating", title=idea.title, source=idea.source.value)
        verdict = await self.provider.evaluate_idea(idea)

        if verdict.approved and verdict.confidence >= 0.5:
            status = ApprovalStatus.APPROVED
        else:
            status = ApprovalStatus.REJECTED

        logger.info(
            "ai_evaluation_complete",
            title=idea.title,
            approved=verdict.approved,
            confidence=verdict.confidence,
            status=status.value,
        )

        return status, verdict

    def enrich_idea(self, idea: RawIdea, verdict: AIVerdict, status: ApprovalStatus, quality_score: float) -> ProcessedIdea:
        """Convert a RawIdea into a ProcessedIdea with AI metadata."""
        return ProcessedIdea(
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
            categories=[verdict.category] if verdict.category and verdict.category != "Other" else [],
            difficulty=verdict.difficulty,
            tech_stack=[idea.language] if idea.language else [],
            status=status,
            ai_confidence=verdict.confidence,
            ai_reasoning=verdict.reasoning,
            quality_score=quality_score,
            fingerprint="",
            discovered_at=idea.created_at or idea.collected_at,
            collected_at=idea.collected_at,
            approved_at=idea.collected_at if status == ApprovalStatus.APPROVED else None,
            dedup_group="",
        )
