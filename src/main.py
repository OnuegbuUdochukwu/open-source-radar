"""Open Source Radar - Main Pipeline Orchestrator.

The daily pipeline:
1. Initialize database
2. Collect ideas from all sources
3. Apply hard rules filtering (Layer 1)
4. Evaluate borderline ideas with AI (Layer 2)
5. Deduplicate (Layer 3)
6. Categorize approved ideas
7. Store results
8. Generate README
9. Compute metrics
10. Check thresholds
11. Publish to GitHub
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog

from src.ai import GeminiProvider, HuggingFaceProvider
from src.ai.openai import OpenAIProvider
from src.ai.anthropic import AnthropicProvider
from src.collectors import GitHubCollector, HackerNewsCollector, RedditCollector
from src.config import settings
from src.database import Database
from src.filters import AIEvaluator, Deduplicator, HardRulesFilter
from src.formatter import READMEGenerator
from src.models import ApprovalStatus, RawIdea
from src.monitoring import AlertManager, GrowthTracker
from src.publisher import GitHubPublisher
from src.storage import IdeaRepository
from src.utils.logging import configure_logging

logger = structlog.get_logger(__name__)


class OpenSourceRadar:
    """Main orchestrator for the entire pipeline."""

    def _resolve_ai_provider(self) -> Any:
        """Resolve the configured AI provider, defaulting to HuggingFace for free tier."""
        provider_map = {
            "gemini": GeminiProvider,
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "huggingface": HuggingFaceProvider,
        }
        provider_cls = provider_map.get(settings.ai_provider, HuggingFaceProvider)

        if provider_cls is GeminiProvider:
            return GeminiProvider()
        if provider_cls is OpenAIProvider:
            return OpenAIProvider()
        if provider_cls is AnthropicProvider:
            return AnthropicProvider()
        return HuggingFaceProvider()

    def __init__(self) -> None:
        configure_logging()

        # Infrastructure
        self.db = Database(settings.db_path)
        self.db.initialize()
        self.repository = IdeaRepository(self.db)

        # Collectors
        self.collectors = [
            GitHubCollector(),
            RedditCollector(),
            HackerNewsCollector(),
        ]

        # Filters
        self.hard_rules = HardRulesFilter()
        ai_provider = self._resolve_ai_provider()
        self.ai_evaluator = AIEvaluator(ai_provider)
        self.deduplicator = Deduplicator(self.db)

        # Services
        self.categorizer = None  # Lazy import to avoid circular deps
        self.readme_generator = READMEGenerator()
        self.publisher = GitHubPublisher()
        self.growth_tracker = GrowthTracker(self.db)
        self.alert_manager = AlertManager(self.db, self.publisher)

    async def run_daily_pipeline(self) -> dict[str, Any]:
        """Execute the full daily collection and publishing pipeline."""
        logger.info("pipeline_started", dry_run=settings.dry_run)

        results = {
            "collected": 0,
            "hard_approved": 0,
            "ai_approved": 0,
            "rejected": 0,
            "duplicates": 0,
            "errors": 0,
            "published": False,
        }

        # Phase 1: Collect
        raw_ideas = await self._collect_all()
        results["collected"] = len(raw_ideas)
        logger.info("phase1_collect_complete", count=len(raw_ideas))

        # Phase 2: Filter (Layers 1, 2, 3)
        approved_ideas = await self._filter_all(raw_ideas)
        results["hard_approved"] = sum(
            1 for idea in raw_ideas
            if self.hard_rules.evaluate(idea) == ApprovalStatus.APPROVED
        )

        # Phase 3: Categorize
        from src.categorizer import CategorizationEngine
        self.categorizer = CategorizationEngine()
        categorized = []
        for idea in approved_ideas:
            categorized.append(self.categorizer.categorize(idea))
            self.repository.store_processed(idea)

        results["ai_approved"] = len(categorized)

        # Phase 4: Store fingerprints for dedup
        for idea in approved_ideas:
            fp = self.deduplicator.compute_fingerprint(idea)
            self.db.save_fingerprint(fp)

        logger.info(
            "pipeline_filter_complete",
            approved=len(categorized),
            rejected=results["rejected"],
            duplicates=results["duplicates"],
        )

        # Phase 5: Generate README
        all_approved = self.repository.get_approved()
        metrics = self.growth_tracker.compute_metrics()
        readme_content = self.readme_generator.generate_readme(
            all_approved,
            metrics.model_dump() if metrics else None,
        )

        # Phase 6: Publish
        if not settings.dry_run:
            pub_success = await self.publisher.publish_readme(readme_content)
            await self.publisher.publish_ideas_json(all_approved)
            results["published"] = pub_success
        else:
            logger.info("dry_mode_skipping_publish")
            self.publisher.write_ideas_json_local(all_approved)
            # Write README locally
            with open("README.md", "w") as f:
                f.write(readme_content)
            results["published"] = True

        # Phase 7: Check thresholds
        await self.alert_manager.check_thresholds(metrics)

        # Done
        logger.info("pipeline_complete", results=results)
        return results

    async def _collect_all(self) -> list[RawIdea]:
        """Collect ideas from all configured sources."""
        all_ideas: list[RawIdea] = []
        tasks = []

        for collector in self.collectors:
            tasks.append(self._collect_from_source(collector))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_ideas.extend(result)
            elif isinstance(result, Exception):
                logger.error("collector_error", error=str(result))

        return all_ideas

    async def _collect_from_source(self, collector: Any) -> list[RawIdea]:
        """Collect from a single source."""
        ideas: list[RawIdea] = []
        try:
            async for idea in collector.collect():
                if idea and idea.title:
                    ideas.append(idea)
            logger.info(
                "source_collected",
                source=collector.source_name,
                count=len(ideas),
            )
        except Exception as e:
            logger.error(
                "source_collect_failed",
                source=collector.source_name,
                error=str(e),
            )
        return ideas

    async def _filter_all(self, ideas: list[RawIdea]) -> list[Any]:
        """Apply all three filter layers."""
        from src.categorizer import CategorizationEngine
        from src.models import ProcessedIdea

        categorized = CategorizationEngine()
        approved_ideas: list = []

        for idea in ideas:
            try:
                # Layer 1: Hard Rules
                hard_status = self.hard_rules.evaluate(idea)

                if hard_status == ApprovalStatus.REJECTED:
                    rejected = ProcessedIdea(
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
                        status=ApprovalStatus.REJECTED,
                        quality_score=self.hard_rules.quality_score(idea),
                        discovered_at=idea.created_at or idea.collected_at,
                        collected_at=idea.collected_at,
                    )
                    self.repository.store_processed(rejected)
                    continue

                # Layer 3: Deduplication (run before AI to save cost)
                is_dup = await self.deduplicator.is_duplicate(idea)
                if is_dup:
                    dup = ProcessedIdea(
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
                        status=ApprovalStatus.DUPLICATE,
                        quality_score=self.hard_rules.quality_score(idea),
                        discovered_at=idea.created_at or idea.collected_at,
                        collected_at=idea.collected_at,
                    )
                    self.repository.store_processed(dup)
                    continue

                quality_score = self.hard_rules.quality_score(idea)

                if hard_status == ApprovalStatus.APPROVED:
                    # Auto-approved by hard rules
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
                        quality_score=quality_score,
                        ai_confidence=1.0,
                        discovered_at=idea.created_at or idea.collected_at,
                        collected_at=idea.collected_at,
                        approved_at=idea.collected_at,
                    )
                    # Categorize using deterministic rules
                    processed = categorized.categorize(processed)
                    self.deduplicator.mark_as_processed(idea, processed)
                    approved_ideas.append(processed)
                    continue

                # Layer 2: AI Evaluation
                ai_status, verdict = await self.ai_evaluator.evaluate(idea)
                processed = self.ai_evaluator.enrich_idea(idea, verdict, ai_status, quality_score)

                if ai_status == ApprovalStatus.APPROVED:
                    self.deduplicator.mark_as_processed(idea, processed)
                    approved_ideas.append(processed)
                else:
                    self.repository.store_processed(processed)

            except Exception as e:
                logger.error("filter_error", title=idea.title, error=str(e))
                continue

        return approved_ideas


async def main() -> None:
    """Entry point for the pipeline."""
    radar = OpenSourceRadar()
    results = await radar.run_daily_pipeline()

    logger.info("main_complete", results=results)

    # Print summary
    print(f"\n{'='*50}")
    print("Open Source Radar - Daily Update Summary")
    print(f"{'='*50}")
    print(f"Collected:     {results['collected']}")
    print(f"Hard Approved: {results['hard_approved']}")
    print(f"AI Approved:   {results['ai_approved']}")
    print(f"Rejected:      {results['rejected']}")
    print(f"Duplicates:    {results['duplicates']}")
    print(f"Published:     {results['published']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
