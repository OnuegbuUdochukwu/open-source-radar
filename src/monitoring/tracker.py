from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from src.database import Database
from src.models import ApprovalStatus, Metrics

logger = structlog.get_logger(__name__)


class GrowthTracker:
    """Tracks repository growth and computes analytics metrics.

    All metrics are stored in the database for historical tracking
    and exported to data/ideas.json for the future web platform.
    """

    def __init__(self, database: Database) -> None:
        self.db = database

    def compute_metrics(self, readme_size_bytes: int = 0) -> Metrics:
        """Compute current metrics from the database."""
        total = self.db.count_processed_ideas()
        approved = self.db.count_processed_ideas(ApprovalStatus.APPROVED)
        rejected = self.db.count_processed_ideas(ApprovalStatus.REJECTED)
        duplicates = self.db.count_processed_ideas(ApprovalStatus.DUPLICATE)

        # Load ideas to compute distributions
        approved_ideas = self.db.get_all_approved_ideas()

        categories: dict[str, int] = {}
        sources: dict[str, int] = {}
        languages: dict[str, int] = {}

        for idea in approved_ideas:
            for cat in idea.categories:
                categories[cat] = categories.get(cat, 0) + 1

            src = idea.source.value
            sources[src] = sources.get(src, 0) + 1

            if idea.language:
                lang = idea.language.lower()
                languages[lang] = languages.get(lang, 0) + 1

        # Growth rate (daily additions over past week)
        growth_rate = self._compute_growth_rate()

        metrics = Metrics(
            total_ideas=total,
            approved_ideas=approved,
            rejected_ideas=rejected,
            duplicate_ideas=duplicates,
            categories=categories,
            sources=sources,
            languages=languages,
            daily_additions=self._get_daily_additions(approved_ideas),
            last_updated=datetime.utcnow(),
            readme_size_bytes=readme_size_bytes,
            growth_rate=growth_rate,
        )

        # Persist metrics
        self.db.save_metrics(metrics)

        return metrics

    def _compute_growth_rate(self) -> float:
        """Compute the 7-day average daily addition rate."""
        previous = self.db.get_metrics()
        if previous is None:
            return 0.0

        # Compute based on daily_additions history
        additions = previous.daily_additions
        if len(additions) < 2:
            return 0.0

        # Average of last 7 days (or however many we have)
        recent = additions[-7:] if len(additions) >= 7 else additions
        total_added = sum(entry.get("count", 0) for entry in recent)
        return total_added / len(recent)

    def _get_daily_additions(self, ideas: list) -> list[dict]:
        """Compute daily addition counts for the last 30 days."""
        from collections import Counter

        today = datetime.utcnow()
        date_counts: Counter = Counter()

        for idea in ideas:
            if idea.approved_at:
                day = idea.approved_at.strftime("%Y-%m-%d")
                date_counts[day] += 1

        # Fill in last 30 days
        result = []
        for i in range(30, -1, -1):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            result.append({"date": day, "count": date_counts.get(day, 0)})

        return result
