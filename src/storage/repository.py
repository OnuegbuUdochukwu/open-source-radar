from __future__ import annotations

from datetime import datetime

import structlog

from src.database import Database
from src.models import ApprovalStatus, ProcessedIdea, RawIdea

logger = structlog.get_logger(__name__)


class IdeaRepository:
    """High-level repository for idea persistence operations.

    Wraps the Database class with business-logic-level operations.
    """

    def __init__(self, database: Database) -> None:
        self.db = database

    def store_raw(self, idea: RawIdea) -> bool:
        """Store a raw collected idea. Returns False if duplicate."""
        try:
            self.db.save_raw_idea(idea)
            return True
        except Exception as e:
            logger.error("store_raw_failed", error=str(e))
            return False

    def store_processed(self, idea: ProcessedIdea) -> bool:
        """Store a processed idea."""
        try:
            self.db.save_processed_idea(idea)
            return True
        except Exception as e:
            logger.error("store_processed_failed", error=str(e))
            return False

    def get_approved(self) -> list[ProcessedIdea]:
        """Get all approved ideas."""
        return self.db.get_all_approved_ideas()

    def get_pending(self) -> list[ProcessedIdea]:
        """Get all pending (unprocessed) ideas."""
        return self.db.get_processed_ideas(status=ApprovalStatus.PENDING)

    def is_processed(self, source_id: str, source: str) -> bool:
        """Check if an idea was already processed."""
        from src.models import SourceType
        try:
            src = SourceType(source)
        except ValueError:
            return False
        return self.db.idea_exists_by_source_id(src, source_id)

    def count_by_status(self, status: ApprovalStatus | None = None) -> int:
        return self.db.count_processed_ideas(status)
