from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.models import (
    Alert,
    ApprovalStatus,
    IdeaFingerprint,
    Metrics,
    ProcessedIdea,
    RawIdea,
    SourceType,
)

logger = structlog.get_logger(__name__)


class Database:
    """SQLite-based persistent storage backend.

    Designed for single-writer (the pipeline). Schema supports the full
    idea lifecycle and future migration to a JSON API / web frontend.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def initialize(self) -> None:
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("database_initialized", path=str(self.db_path))

    def save_raw_idea(self, idea: RawIdea) -> int:
        conn = self.connect()
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO raw_ideas
                (id, source, source_id, title, description, url, author,
                 score, stars, forks, language, topics, comments,
                 created_at, updated_at, collected_at, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idea.id,
                idea.source.value,
                idea.source_id,
                idea.title,
                idea.description,
                idea.url,
                idea.author,
                idea.score,
                idea.stars,
                idea.forks,
                idea.language,
                json.dumps(idea.topics),
                idea.comments,
                idea.created_at.isoformat() if idea.created_at else None,
                idea.updated_at.isoformat() if idea.updated_at else None,
                idea.collected_at.isoformat(),
                json.dumps(idea.raw_data),
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def idea_exists_by_source_id(self, source: SourceType, source_id: str) -> bool:
        conn = self.connect()
        cursor = conn.execute(
            "SELECT 1 FROM processed_ideas WHERE source = ? AND source_id = ? LIMIT 1",
            (source.value, source_id),
        )
        return cursor.fetchone() is not None

    def save_processed_idea(self, idea: ProcessedIdea) -> int:
        conn = self.connect()
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO processed_ideas
                (id, source, source_id, title, description, url, author,
                 score, stars, forks, language, topics, comments,
                 categories, difficulty, tech_stack, status,
                 ai_confidence, ai_reasoning, quality_score, fingerprint,
                 discovered_at, collected_at, approved_at, dedup_group)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idea.id,
                idea.source.value,
                idea.source_id,
                idea.title,
                idea.description,
                idea.url,
                idea.author,
                idea.score,
                idea.stars,
                idea.forks,
                idea.language,
                json.dumps(idea.topics),
                idea.comments,
                json.dumps(idea.categories),
                idea.difficulty.value,
                json.dumps(idea.tech_stack),
                idea.status.value,
                idea.ai_confidence,
                idea.ai_reasoning,
                idea.quality_score,
                idea.fingerprint,
                idea.discovered_at.isoformat() if idea.discovered_at else None,
                idea.collected_at.isoformat(),
                idea.approved_at.isoformat() if idea.approved_at else None,
                idea.dedup_group,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def get_processed_ideas(
        self,
        status: ApprovalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProcessedIdea]:
        conn = self.connect()
        if status:
            cursor = conn.execute(
                "SELECT * FROM processed_ideas WHERE status = ? ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
                (status.value, limit, offset),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM processed_ideas ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [self._row_to_processed_idea(row) for row in cursor.fetchall()]

    def count_processed_ideas(self, status: ApprovalStatus | None = None) -> int:
        conn = self.connect()
        if status:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM processed_ideas WHERE status = ?",
                (status.value,),
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM processed_ideas")
        return cursor.fetchone()[0]

    def get_all_approved_ideas(self) -> list[ProcessedIdea]:
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM processed_ideas WHERE status = ? ORDER BY discovered_at DESC",
            (ApprovalStatus.APPROVED.value,),
        )
        return [self._row_to_processed_idea(row) for row in cursor.fetchall()]

    def _row_to_processed_idea(self, row: sqlite3.Row) -> ProcessedIdea:
        d = dict(row)
        return ProcessedIdea(
            id=d["id"],
            source=SourceType(d["source"]),
            source_id=d["source_id"],
            title=d["title"],
            description=d["description"] or "",
            url=d["url"] or "",
            author=d["author"] or "",
            score=d["score"] or 0,
            stars=d["stars"] or 0,
            forks=d["forks"] or 0,
            language=d["language"] or "",
            topics=json.loads(d["topics"]) if d["topics"] else [],
            comments=d["comments"] or 0,
            categories=json.loads(d["categories"]) if d["categories"] else [],
            difficulty=d["difficulty"] or "Intermediate",
            tech_stack=json.loads(d["tech_stack"]) if d["tech_stack"] else [],
            status=ApprovalStatus(d["status"]) if d["status"] else ApprovalStatus.PENDING,
            ai_confidence=d["ai_confidence"] or 0.0,
            ai_reasoning=d["ai_reasoning"] or "",
            quality_score=d["quality_score"] or 0.0,
            fingerprint=d["fingerprint"] or "",
            discovered_at=datetime.fromisoformat(d["discovered_at"]) if d.get("discovered_at") else datetime.utcnow(),
            collected_at=datetime.fromisoformat(d["collected_at"]) if d.get("collected_at") else datetime.utcnow(),
            approved_at=datetime.fromisoformat(d["approved_at"]) if d.get("approved_at") else None,
            dedup_group=d["dedup_group"] or "",
        )

    # --- Fingerprint / Dedup ---
    def save_fingerprint(self, fp: IdeaFingerprint) -> None:
        conn = self.connect()
        conn.execute(
            """INSERT OR IGNORE INTO fingerprints
               (idea_id, title_exact, title_fuzzy, url, source_id, embedding, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                fp.idea_id,
                fp.title_exact,
                fp.title_fuzzy,
                fp.url,
                fp.source_id,
                json.dumps(fp.embedding),
                fp.created_at.isoformat(),
            ),
        )
        conn.commit()

    def find_exact_title_match(self, title: str) -> bool:
        conn = self.connect()
        cursor = conn.execute(
            "SELECT 1 FROM fingerprints WHERE title_exact = ? LIMIT 1",
            (title.lower().strip(),),
        )
        return cursor.fetchone() is not None

    def find_url_match(self, url: str) -> bool:
        conn = self.connect()
        cursor = conn.execute(
            "SELECT 1 FROM fingerprints WHERE url = ? LIMIT 1",
            (url,),
        )
        return cursor.fetchone() is not None

    def find_source_id_match(self, source_id: str) -> bool:
        conn = self.connect()
        cursor = conn.execute(
            "SELECT 1 FROM fingerprints WHERE source_id = ? LIMIT 1",
            (source_id,),
        )
        return cursor.fetchone() is not None

    def get_all_embeddings(self) -> list[tuple[str, list[float]]]:
        conn = self.connect()
        cursor = conn.execute(
            "SELECT idea_id, embedding FROM fingerprints WHERE embedding IS NOT NULL AND embedding != '[]'"
        )
        result = []
        for row in cursor.fetchall():
            emb = json.loads(row["embedding"])
            if emb:
                result.append((row["idea_id"], emb))
        return result

    # --- Alerts ---
    def save_alert(self, alert: Alert) -> None:
        conn = self.connect()
        conn.execute(
            """INSERT OR REPLACE INTO alerts
               (id, level, message, metric, value, threshold, created_at, resolved, github_issue_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.id,
                alert.level,
                alert.message,
                alert.metric,
                alert.value,
                alert.threshold,
                alert.created_at.isoformat(),
                int(alert.resolved),
                alert.github_issue_url,
            ),
        )
        conn.commit()

    def get_active_alerts(self) -> list[Alert]:
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM alerts WHERE resolved = 0 ORDER BY created_at DESC"
        )
        return [Alert(**dict(row)) for row in cursor.fetchall()]

    # --- Metrics ---
    def save_metrics(self, metrics: Metrics) -> None:
        conn = self.connect()
        conn.execute(
            """INSERT OR REPLACE INTO metrics
               (id, total_ideas, approved_ideas, rejected_ideas, duplicate_ideas,
                categories, sources, languages, daily_additions,
                last_updated, readme_size_bytes, growth_rate)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metrics.total_ideas,
                metrics.approved_ideas,
                metrics.rejected_ideas,
                metrics.duplicate_ideas,
                json.dumps(metrics.categories),
                json.dumps(metrics.sources),
                json.dumps(metrics.languages),
                json.dumps(metrics.daily_additions),
                metrics.last_updated.isoformat(),
                metrics.readme_size_bytes,
                metrics.growth_rate,
            ),
        )
        conn.commit()

    def get_metrics(self) -> Metrics | None:
        conn = self.connect()
        cursor = conn.execute("SELECT * FROM metrics WHERE id = 1")
        row = cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        return Metrics(
            total_ideas=d["total_ideas"],
            approved_ideas=d["approved_ideas"],
            rejected_ideas=d["rejected_ideas"],
            duplicate_ideas=d["duplicate_ideas"],
            categories=json.loads(d["categories"]) if d["categories"] else {},
            sources=json.loads(d["sources"]) if d["sources"] else {},
            languages=json.loads(d["languages"]) if d["languages"] else {},
            daily_additions=json.loads(d["daily_additions"]) if d["daily_additions"] else [],
            last_updated=datetime.fromisoformat(d["last_updated"]) if d.get("last_updated") else datetime.utcnow(),
            readme_size_bytes=d["readme_size_bytes"] or 0,
            growth_rate=d["growth_rate"] or 0.0,
        )


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_ideas (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    url TEXT DEFAULT '',
    author TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    language TEXT DEFAULT '',
    topics TEXT DEFAULT '[]',
    comments INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    collected_at TEXT NOT NULL,
    raw_data TEXT DEFAULT '{}',
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS processed_ideas (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT DEFAULT '',
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    url TEXT DEFAULT '',
    author TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    language TEXT DEFAULT '',
    topics TEXT DEFAULT '[]',
    comments INTEGER DEFAULT 0,
    categories TEXT DEFAULT '[]',
    difficulty TEXT DEFAULT 'Intermediate',
    tech_stack TEXT DEFAULT '[]',
    status TEXT DEFAULT 'pending',
    ai_confidence REAL DEFAULT 0.0,
    ai_reasoning TEXT DEFAULT '',
    quality_score REAL DEFAULT 0.0,
    fingerprint TEXT DEFAULT '',
    discovered_at TEXT,
    collected_at TEXT NOT NULL,
    approved_at TEXT,
    dedup_group TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_processed_status ON processed_ideas(status);
CREATE INDEX IF NOT EXISTS idx_processed_source ON processed_ideas(source);
CREATE INDEX IF NOT EXISTS idx_processed_discovered ON processed_ideas(discovered_at);

CREATE TABLE IF NOT EXISTS fingerprints (
    idea_id TEXT PRIMARY KEY,
    title_exact TEXT NOT NULL,
    title_fuzzy TEXT NOT NULL,
    url TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    embedding TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fingerprint_title ON fingerprints(title_exact);
CREATE INDEX IF NOT EXISTS idx_fingerprint_url ON fingerprints(url);
CREATE INDEX IF NOT EXISTS idx_fingerprint_source_id ON fingerprints(source_id);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    metric TEXT DEFAULT '',
    value REAL DEFAULT 0.0,
    threshold REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    github_issue_url TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY DEFAULT 1,
    total_ideas INTEGER DEFAULT 0,
    approved_ideas INTEGER DEFAULT 0,
    rejected_ideas INTEGER DEFAULT 0,
    duplicate_ideas INTEGER DEFAULT 0,
    categories TEXT DEFAULT '{}',
    sources TEXT DEFAULT '{}',
    languages TEXT DEFAULT '{}',
    daily_additions TEXT DEFAULT '[]',
    last_updated TEXT NOT NULL,
    readme_size_bytes INTEGER DEFAULT 0,
    growth_rate REAL DEFAULT 0.0
);
"""
