from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from src.models import RawIdea


class BaseCollector(ABC):
    """Abstract base for all source collectors.

    Each collector implements a single source type and yields RawIdea objects
    for the pipeline to process. New sources (Dev.to, Product Hunt, etc.)
    simply implement this interface.
    """

    source_name: str = "base"

    @abstractmethod
    async def collect(self) -> AsyncIterator[RawIdea]:
        """Collect ideas from the source. Yields RawIdea items."""
        if False:
            yield  # pragma: no cover

    @abstractmethod
    async def validate_source(self) -> bool:
        """Check if the source is reachable and credentials are valid."""
        ...
