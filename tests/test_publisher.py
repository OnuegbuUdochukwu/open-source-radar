from __future__ import annotations

from datetime import datetime

from src.formatter.readme_generator import READMEGenerator
from src.models import ApprovalStatus, DifficultyLevel, ProcessedIdea, SourceType


class TestREADMEGenerator:
    def test_generate_empty_readme(self):
        gen = READMEGenerator()
        content = gen.generate_readme([])
        assert "# Open Source Ideas" in content
        assert "Stats" in content
        assert "Table of Contents" in content
        assert "Automatically generated" in content

    def test_generate_with_ideas(self, sample_processed_idea):
        gen = READMEGenerator()
        content = gen.generate_readme([sample_processed_idea])

        assert sample_processed_idea.title in content
        assert sample_processed_idea.description[:50] in content
        assert sample_processed_idea.source.value.title() in content
        assert sample_processed_idea.difficulty.value in content

    def test_generate_with_metrics(self, sample_processed_idea):
        gen = READMEGenerator()
        metrics = {
            "total_ideas": 100,
            "approved_ideas": 75,
            "categories": {"Python": 30, "Web": 25},
            "last_updated": "2024-06-15",
        }
        content = gen.generate_readme([sample_processed_idea], metrics)

        assert "100" in content
        assert "75" in content

    def test_category_section_placement(self):
        gen = READMEGenerator()

        python_idea = ProcessedIdea(
            id="py-1",
            source=SourceType.GITHUB,
            source_id="1",
            title="Python Tool",
            description="A Python CLI tool",
            url="https://github.com/test/py-tool",
            author="test",
            score=50,
            stars=50,
            forks=5,
            language="Python",
            topics=["python"],
            comments=0,
            categories=["Python"],
            difficulty=DifficultyLevel.INTERMEDIATE,
            status=ApprovalStatus.APPROVED,
            discovered_at=datetime(2024, 1, 1),
            collected_at=datetime(2024, 6, 15),
        )

        content = gen.generate_readme([python_idea])

        # Should be in the Python section
        assert "## Python" in content
        assert "Python Tool" in content

    def test_entry_formatting(self, sample_processed_idea):
        gen = READMEGenerator()
        content = gen.generate_readme([sample_processed_idea])

        # Check consistent format
        assert "### " in content  # Title heading
        assert "**Source:**" in content  # Source badge
        assert "**Tech Stack:**" in content  # Tech stack
        assert "**Difficulty:**" in content  # Difficulty
        assert "http" in content  # URL link

    def test_formatted_idea(self):
        """Test an AI-enhanced project (more complete metadata)."""
        idea = ProcessedIdea(
            id="ai-1",
            source=SourceType.REDDIT,
            source_id="reddit-1",
            title="AI-Powered Resume Analyzer",
            description="An NLP tool that analyzes resumes and provides suggestions",
            url="https://reddit.com/r/opensource/comments/ai-resume",
            author="devuser",
            score=150,
            stars=0,
            forks=0,
            language="Python",
            topics=["nlp", "ai", "resume"],
            comments=25,
            categories=["AI/ML", "Python", "Web Applications"],
            difficulty=DifficultyLevel.INTERMEDIATE,
            tech_stack=["Python", "NLP", "Flask"],
            status=ApprovalStatus.APPROVED,
            ai_confidence=0.95,
            ai_reasoning="Good project idea",
            quality_score=85.0,
            discovered_at=datetime(2024, 1, 1),
            collected_at=datetime(2024, 6, 15),
            approved_at=datetime(2024, 6, 15),
        )

        gen = READMEGenerator()
        content = gen.generate_readme([idea])

        assert "AI-Powered Resume Analyzer" in content
        assert "Python" in content
        assert "NLP" in content
