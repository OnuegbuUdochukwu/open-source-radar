from __future__ import annotations

from datetime import datetime

import pytest

from src.database import Database
from src.models import (
    Alert,
    ApprovalStatus,
    IdeaFingerprint,
    Metrics,
    ProcessedIdea,
    RawIdea,
    SourceType,
)


class TestDatabase:
    def test_initialize(self, db: Database):
        """Verify all tables are created."""
        conn = db.connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [row["name"] for row in tables]
        assert "raw_ideas" in table_names
        assert "processed_ideas" in table_names
        assert "fingerprints" in table_names
        assert "alerts" in table_names
        assert "metrics" in table_names

    def test_save_raw_idea(self, db: Database, sample_raw_github_idea: RawIdea):
        db.save_raw_idea(sample_raw_github_idea)
        conn = db.connect()
        row = conn.execute("SELECT * FROM raw_ideas WHERE id = ?", (sample_raw_github_idea.id,)).fetchone()
        assert row is not None
        assert row["title"] == "awesome-project"
        assert row["source"] == "github"

    def test_idea_exists_by_source_id(self, db: Database, sample_processed_idea: ProcessedIdea):
        db.save_processed_idea(sample_processed_idea)
        assert db.idea_exists_by_source_id(SourceType.GITHUB, "12345") is True
        assert db.idea_exists_by_source_id(SourceType.GITHUB, "nonexistent") is False

    def test_save_processed_idea(self, db: Database, sample_processed_idea: ProcessedIdea):
        db.save_processed_idea(sample_processed_idea)
        conn = db.connect()
        row = conn.execute("SELECT * FROM processed_ideas WHERE id = ?", (sample_processed_idea.id,)).fetchone()
        assert row is not None
        assert row["status"] == "approved"
        assert row["ai_confidence"] == 0.92

    def test_get_all_approved_ideas(self, db: Database):
        idea1 = sample_processed(ApprovalStatus.APPROVED)
        idea2 = sample_processed(ApprovalStatus.APPROVED)
        idea3 = sample_processed(ApprovalStatus.REJECTED)
        db.save_processed_idea(idea1)
        db.save_processed_idea(idea2)
        db.save_processed_idea(idea3)

        approved = db.get_all_approved_ideas()
        assert len(approved) == 2

    def test_count_by_status(self, db: Database):
        db.save_processed_idea(sample_processed(ApprovalStatus.APPROVED))
        db.save_processed_idea(sample_processed(ApprovalStatus.REJECTED))
        db.save_processed_idea(sample_processed(ApprovalStatus.DUPLICATE))

        assert db.count_processed_ideas(ApprovalStatus.APPROVED) == 1
        assert db.count_processed_ideas(ApprovalStatus.REJECTED) == 1
        assert db.count_processed_ideas() == 3

    def test_fingerprint_operations(self, db: Database):
        fp = IdeaFingerprint(
            idea_id="fp-1",
            title_exact="test project",
            title_fuzzy="project test",
            url="https://github.com/test/project",
            source_id="src-1",
            embedding=[0.1, 0.2, 0.3],
        )
        db.save_fingerprint(fp)

        assert db.find_exact_title_match("test project") is True
        assert db.find_exact_title_match("other") is False
        assert db.find_url_match("https://github.com/test/project") is True
        assert db.find_source_id_match("src-1") is True

        embeddings = db.get_all_embeddings()
        assert len(embeddings) == 1
        assert embeddings[0][0] == "fp-1"
        assert embeddings[0][1] == [0.1, 0.2, 0.3]

    def test_alerts(self, db: Database):
        alert = Alert(
            id="alert-1",
            level="warning",
            message="README size too large",
            metric="readme_size",
            value=600.0,
            threshold=500.0,
        )
        db.save_alert(alert)

        active = db.get_active_alerts()
        assert len(active) == 1
        assert active[0].level == "warning"
        assert active[0].metric == "readme_size"

    def test_metrics(self, db: Database):
        metrics = Metrics(
            total_ideas=100,
            approved_ideas=75,
            rejected_ideas=20,
            duplicate_ideas=5,
            categories={"Python": 30, "Web": 25},
            sources={"github": 50, "reddit": 25},
            languages={"python": 30, "javascript": 20},
            readme_size_bytes=10240,
            growth_rate=2.5,
        )
        db.save_metrics(metrics)

        loaded = db.get_metrics()
        assert loaded is not None
        assert loaded.total_ideas == 100
        assert loaded.approved_ideas == 75
        assert loaded.categories["Python"] == 30
        assert loaded.growth_rate == 2.5

    def test_deduplication_persistence(self, db: Database):
        """Verify dedup state persists across instances."""
        fp = IdeaFingerprint(
            idea_id="persist-test",
            title_exact="unique project",
            title_fuzzy="project unique",
            url="https://github.com/u/p",
            source_id="sp-1",
        )
        db.save_fingerprint(fp)

        db2 = Database(":memory:")
        db2.initialize()
        assert db2.find_exact_title_match("unique project") is False


def sample_processed(status: ApprovalStatus) -> ProcessedIdea:
    import uuid
    return ProcessedIdea(
        id=uuid.uuid4().hex,
        source=SourceType.GITHUB,
        source_id=str(uuid.uuid4()),
        title=f"Project {status.value}",
        description="A test project",
        url="https://github.com/test/project",
        author="test",
        score=100,
        stars=100,
        forks=20,
        language="Python",
        topics=[],
        comments=0,
        status=status,
        discovered_at=datetime(2024, 1, 1),
        collected_at=datetime(2024, 6, 15),
    )
