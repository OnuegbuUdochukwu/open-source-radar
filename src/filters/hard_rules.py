from __future__ import annotations

import structlog

from src.config import settings
from src.models import ApprovalStatus, RawIdea, SourceType

logger = structlog.get_logger(__name__)


class HardRulesFilter:
    """Layer 1: Hard rules that bypass AI evaluation.

    Projects exceeding viral thresholds are auto-approved.
    Projects below minimum thresholds are auto-rejected.
    Everything else proceeds to Layer 2 (AI evaluation).
    """

    def evaluate(self, idea: RawIdea) -> ApprovalStatus:
        """Determine status based on hard rules only.

        Returns:
            APPROVED: idea exceeds viral threshold
            REJECTED: idea below minimum threshold
            PENDING: needs further evaluation (AI layer)
        """
        threshold = self._get_thresholds(idea.source)

        if idea.score >= threshold["viral"]:
            logger.info("hard_rule_approved", title=idea.title, score=idea.score, source=idea.source.value)
            return ApprovalStatus.APPROVED

        if idea.score < threshold["minimum"]:
            logger.info("hard_rule_rejected", title=idea.title, score=idea.score, source=idea.source.value)
            return ApprovalStatus.REJECTED

        return ApprovalStatus.PENDING

    def _get_thresholds(self, source: SourceType) -> dict[str, int]:
        if source == SourceType.GITHUB:
            return {
                "viral": settings.github_stars_viral,
                "minimum": settings.github_stars_minimum,
            }
        elif source == SourceType.REDDIT:
            return {
                "viral": settings.reddit_upvotes_viral,
                "minimum": settings.reddit_upvotes_minimum,
            }
        else:
            return {
                "viral": settings.hackernews_score_viral,
                "minimum": settings.hackernews_score_minimum,
            }

    def quality_score(self, idea: RawIdea) -> float:
        """Calculate a quality score from 0-100 for ranking."""
        score = 0.0

        # Has description (0-20)
        if idea.description and len(idea.description) > 50:
            score += 20
        elif idea.description:
            score += 10

        # Has meaningful title (0-10)
        if len(idea.title) > 10:
            score += 10

        # Score/stars contribution (0-30)
        relative_score = min(idea.score / 100, 1.0)
        score += relative_score * 30

        # Has language/tech info (0-15)
        if idea.language:
            score += 10
        if idea.topics:
            score += 5

        # Source-specific signals
        if idea.source == SourceType.GITHUB:
            # Has stars and forks (0-15)
            if idea.forks > 0:
                score += 7
            if idea.language:
                score += 8
        elif idea.source == SourceType.REDDIT:
            # Has comments (engagement) (0-15)
            score += min(idea.comments / 20, 1.0) * 15
        else:
            # HN: points + comments (0-15)
            score += min((idea.score + idea.comments) / 50, 1.0) * 15

        # Author presence (0-10)
        if idea.author and idea.author not in ("[deleted]", "AutoModerator"):
            score += 10

        return min(score, 100.0)
