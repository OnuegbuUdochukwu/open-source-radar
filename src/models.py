from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    GITHUB = "github"
    REDDIT = "reddit"
    HACKER_NEWS = "hackernews"


class DifficultyLevel(str, Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class AIVerdict(BaseModel):
    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    category: str = ""
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    summary: str = ""
    reasoning: str = ""


class RawIdea(BaseModel):
    """Idea collected from a source before any filtering."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    source: SourceType
    source_id: str = ""
    title: str
    description: str = ""
    url: str = ""
    author: str = ""
    score: int = 0
    stars: int = 0
    forks: int = 0
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    comments: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    collected_at: datetime | None = Field(default_factory=datetime.utcnow)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ProcessedIdea(BaseModel):
    """Idea after going through the full pipeline."""

    id: str
    source: SourceType
    source_id: str
    title: str
    description: str
    url: str
    author: str
    score: int
    stars: int
    forks: int
    language: str
    topics: list[str]
    comments: int
    categories: list[str] = Field(default_factory=list)
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    tech_stack: list[str] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    ai_confidence: float = 0.0
    ai_reasoning: str = ""
    quality_score: float = 0.0
    fingerprint: str = ""
    discovered_at: datetime
    collected_at: datetime
    approved_at: datetime | None = None
    dedup_group: str = ""

    def to_json_entry(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.categories,
            "difficulty": self.difficulty.value,
            "tech_stack": self.tech_stack,
            "description": self.description,
            "source": self.source.value,
            "url": self.url,
            "language": self.language,
            "stars": self.stars,
            "score": self.score,
            "author": self.author,
            "created_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }


class Category(BaseModel):
    name: str
    slug: str
    parent: str | None = None


class Metrics(BaseModel):
    total_ideas: int = 0
    approved_ideas: int = 0
    rejected_ideas: int = 0
    duplicate_ideas: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    sources: dict[str, int] = Field(default_factory=dict)
    languages: dict[str, int] = Field(default_factory=dict)
    daily_additions: list[dict[str, Any]] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    readme_size_bytes: int = 0
    growth_rate: float = 0.0


class Alert(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    level: str  # "warning" or "critical"
    message: str
    metric: str
    value: float
    threshold: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    github_issue_url: str = ""


class IdeaFingerprint(BaseModel):
    """Used for deduplication."""

    idea_id: str
    title_exact: str
    title_fuzzy: str
    url: str
    source_id: str
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
