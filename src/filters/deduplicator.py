from __future__ import annotations

import re
from typing import Any

import numpy as np
import structlog
from thefuzz import fuzz

from src.config import settings
from src.database import Database
from src.models import IdeaFingerprint, ProcessedIdea, RawIdea

logger = structlog.get_logger(__name__)


class Deduplicator:
    """Layer 3: Deduplication engine.

    Uses multiple strategies:
    1. Exact title matching (O(1) lookup)
    2. Fuzzy title matching (Levenshtein ratio)
    3. URL matching (exact URL check)
    4. Source ID matching (same original post)
    5. Semantic similarity (embedding-based, optional)
    """

    def __init__(self, database: Database) -> None:
        self.db = database
        self._embedding_model: Any = None

    def _get_embedding_model(self) -> Any:
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("embedding_model_loaded")
            except ImportError:
                logger.warning("sentence_transformers_not_available")
                return None
        return self._embedding_model

    def compute_fingerprint(self, idea: RawIdea) -> IdeaFingerprint:
        """Compute a fingerprint for an idea."""
        normalized_title = self._normalize_title(idea.title)
        return IdeaFingerprint(
            idea_id=idea.id,
            title_exact=normalized_title,
            title_fuzzy=self._fuzzy_key(normalized_title),
            url=idea.url.strip().rstrip("/"),
            source_id=idea.source_id,
        )

    async def is_duplicate(self, idea: RawIdea) -> bool:
        """Check if an idea is a duplicate using all available methods."""
        # 1. Source ID check (fastest)
        if idea.source_id and self.db.find_source_id_match(idea.source_id):
            logger.info("duplicate_source_id", title=idea.title, source_id=idea.source_id)
            return True

        # 2. Exact URL check
        if idea.url and self.db.find_url_match(idea.url.strip().rstrip("/")):
            logger.info("duplicate_url", title=idea.title, url=idea.url)
            return True

        # 3. Exact title match
        normalized = self._normalize_title(idea.title)
        if self.db.find_exact_title_match(normalized):
            logger.info("duplicate_exact_title", title=idea.title)
            return True

        # 4. Fuzzy title match against existing entries
        if await self._fuzzy_title_match(idea.title):
            logger.info("duplicate_fuzzy_title", title=idea.title)
            return True

        # 5. Semantic similarity (most expensive, last resort)
        if await self._semantic_match(idea):
            logger.info("duplicate_semantic", title=idea.title)
            return True

        return False

    async def _fuzzy_title_match(self, title: str) -> bool:
        """Check fuzzy title similarity against existing fingerprints."""
        normalized = self._normalize_title(title)
        fuzzy_key = self._fuzzy_key(normalized)

        # Quick check: if a fingerprint with identical fuzzy key exists
        # We use thefuzz for a more thorough check
        conn = self.db.connect()
        cursor = conn.execute(
            "SELECT title_exact FROM fingerprints"
        )
        for row in cursor.fetchall():
            existing = row["title_exact"]
            ratio = fuzz.ratio(fuzzy_key, self._fuzzy_key(existing))
            partial = fuzz.partial_ratio(fuzzy_key, self._fuzzy_key(existing))
            if ratio >= 85 or partial >= 90:
                return True

        return False

    async def _semantic_match(self, idea: RawIdea) -> bool:
        """Check semantic similarity using sentence embeddings."""
        model = self._get_embedding_model()
        if model is None:
            return False

        all_embeddings = self.db.get_all_embeddings()
        if not all_embeddings:
            return False

        text = f"{idea.title} {idea.description[:500]}"
        embedding = model.encode(text, normalize_embeddings=True)

        threshold = settings.similarity_threshold
        for idea_id, existing_emb in all_embeddings:
            existing_np = np.array(existing_emb)
            if existing_np.shape != embedding.shape:
                continue
            similarity = float(np.dot(embedding, existing_np))
            if similarity >= threshold:
                logger.info(
                    "semantic_duplicate_found",
                    idea_id=idea_id,
                    similarity=similarity,
                    threshold=threshold,
                )
                return True

        return False

    def compute_embedding(self, idea: RawIdea) -> list[float]:
        """Compute semantic embedding for an idea."""
        model = self._get_embedding_model()
        if model is None:
            return []

        text = f"{idea.title} {idea.description[:500]}"
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for consistent matching."""
        normalized = title.lower().strip()
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _fuzzy_key(self, title: str) -> str:
        """Create a key optimized for fuzzy matching."""
        words = title.split()
        words.sort()
        return " ".join(words)

    def mark_as_processed(
        self,
        idea: RawIdea,
        processed: ProcessedIdea,
        embedding: list[float] | None = None,
    ) -> None:
        """Record an idea as processed to prevent future duplicates."""
        fp = self.compute_fingerprint(idea)
        if embedding:
            fp.embedding = embedding
        self.db.save_fingerprint(fp)
        self.db.save_processed_idea(processed)
