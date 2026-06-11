from __future__ import annotations

from src.categorizer.engine import CategorizationEngine
from src.models import ApprovalStatus, DifficultyLevel, ProcessedIdea, SourceType
from datetime import datetime


def test_categorize_python_project():
    idea = ProcessedIdea(
        id="1",
        source=SourceType.GITHUB,
        source_id="1",
        title="Django Blog Engine",
        description="A blog engine built with Django and Python",
        url="https://github.com/test/blog",
        author="test",
        score=50,
        stars=50,
        forks=10,
        language="Python",
        topics=["django", "blog", "web"],
        comments=0,
        status=ApprovalStatus.APPROVED,
        discovered_at=datetime(2024, 1, 1),
        collected_at=datetime(2024, 6, 15),
    )
    engine = CategorizationEngine()
    result = engine.categorize(idea)

    assert "Python" in result.categories
    assert "Web Applications" in result.categories or "Developer Tools" in result.categories
    assert "Python" in result.tech_stack


def test_categorize_ai_project():
    idea = ProcessedIdea(
        id="2",
        source=SourceType.GITHUB,
        source_id="2",
        title="Neural Network from Scratch",
        description="Building a neural network library using PyTorch",
        url="https://github.com/test/nn",
        author="test",
        score=100,
        stars=100,
        forks=30,
        language="Python",
        topics=["deep-learning", "neural-networks", "ai"],
        comments=0,
        difficulty=DifficultyLevel.ADVANCED,
        status=ApprovalStatus.APPROVED,
        discovered_at=datetime(2024, 1, 1),
        collected_at=datetime(2024, 6, 15),
    )
    engine = CategorizationEngine()
    result = engine.categorize(idea)

    assert "AI/ML" in result.categories or "AI Projects" in result.categories
    assert "Python" in result.categories


def test_categorize_beginner_project():
    idea = ProcessedIdea(
        id="3",
        source=SourceType.GITHUB,
        source_id="3",
        title="Hello World React App",
        description="A getting-started tutorial for React beginners",
        url="https://github.com/test/react-hello",
        author="test",
        score=10,
        stars=10,
        forks=2,
        language="JavaScript",
        topics=["react", "beginner", "tutorial"],
        comments=0,
        status=ApprovalStatus.APPROVED,
        discovered_at=datetime(2024, 1, 1),
        collected_at=datetime(2024, 6, 15),
    )
    engine = CategorizationEngine()
    result = engine.categorize(idea)

    assert "React" in result.categories
    assert "JavaScript" in result.categories
    assert result.difficulty == DifficultyLevel.BEGINNER


def test_categorize_fallback():
    idea = ProcessedIdea(
        id="4",
        source=SourceType.GITHUB,
        source_id="4",
        title="Some Random Thing",
        description="",
        url="https://github.com/test/random",
        author="test",
        score=1,
        stars=1,
        forks=0,
        language="",
        topics=[],
        comments=0,
        status=ApprovalStatus.APPROVED,
        discovered_at=datetime(2024, 1, 1),
        collected_at=datetime(2024, 6, 15),
    )
    engine = CategorizationEngine()
    result = engine.categorize(idea)

    assert "Other" in result.categories


def test_tech_stack_extraction():
    idea = ProcessedIdea(
        id="5",
        source=SourceType.GITHUB,
        source_id="5",
        title="Full Stack App",
        description="Built with React, Node.js, PostgreSQL, and Docker",
        url="https://github.com/test/fullstack",
        author="test",
        score=80,
        stars=80,
        forks=15,
        language="TypeScript",
        topics=["react", "node"],
        comments=0,
        status=ApprovalStatus.APPROVED,
        discovered_at=datetime(2024, 1, 1),
        collected_at=datetime(2024, 6, 15),
    )
    engine = CategorizationEngine()
    result = engine.categorize(idea)

    assert "TypeScript" in result.tech_stack
    assert any("React" in t for t in result.tech_stack)
    assert any("node" in t.lower() for t in result.tech_stack)
