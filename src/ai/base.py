from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import AIVerdict, RawIdea


class AIProvider(ABC):
    """Abstract interface for AI evaluation providers.

    Implementations can wrap Gemini, OpenAI, Anthropic, or local models.
    The pipeline plugs in whichever provider is configured.
    """

    provider_name: str = "base"

    @abstractmethod
    async def evaluate_idea(self, idea: RawIdea) -> AIVerdict:
        """Evaluate whether a project idea is worth including.

        The AI must assess:
        - Is this a legitimate project idea?
        - Is it unique?
        - Is it useful?
        - Is it educational?
        - Is it not spam?
        - Is it not a duplicate of existing entries?

        Returns AIVerdict with approval decision and metadata.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the AI provider is available and API keys are valid."""
        ...
