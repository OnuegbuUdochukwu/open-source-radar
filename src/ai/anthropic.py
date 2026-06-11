from __future__ import annotations

import json
import re
from typing import Any

import anthropic
import structlog

from src.ai.base import AIProvider
from src.config import settings
from src.models import AIVerdict, DifficultyLevel, RawIdea
from src.utils.retry import async_retry

logger = structlog.get_logger(__name__)

EVALUATION_PROMPT = """You are an expert curator evaluating open-source project ideas.

Analyze this project idea and determine if it should be featured.

Idea Title: {title}
Description: {description}
Source: {source}
Language/Tech: {language}
Score: {score}
Topics: {topics}

Respond ONLY with a JSON object:
{{
    "approved": true/false,
    "confidence": 0.0-1.0,
    "category": "...",
    "difficulty": "Beginner | Intermediate | Advanced",
    "summary": "...",
    "reasoning": "..."
}}"""


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider for idea evaluation."""

    provider_name = "anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False

    @async_retry()
    async def evaluate_idea(self, idea: RawIdea) -> AIVerdict:
        if not self.api_key:
            logger.warning("anthropic_no_api_key")
            return AIVerdict(approved=False, confidence=0.0, category="Other")

        client = self._get_client()
        prompt = EVALUATION_PROMPT.format(
            title=idea.title[:500],
            description=idea.description[:1000] or "No description",
            source=idea.source.value,
            language=idea.language or "Not specified",
            score=idea.score,
            topics=", ".join(idea.topics[:10]) or "None",
        )

        try:
            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                temperature=0.1,
                system="You are a JSON-only API. Respond with valid JSON only, no markdown.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else "{}"
            return self._parse_response(text, idea)
        except Exception as e:
            logger.error("anthropic_evaluation_error", error=str(e), title=idea.title)
            return AIVerdict(approved=False, confidence=0.0, category="Other", reasoning=str(e)[:200])

    def _parse_response(self, text: str, idea: RawIdea) -> AIVerdict:
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            return AIVerdict(approved=False, confidence=0.0, category="Other", reasoning="Invalid JSON")

        difficulty_str = data.get("difficulty", "Intermediate")
        try:
            difficulty = DifficultyLevel(difficulty_str)
        except ValueError:
            difficulty = DifficultyLevel.INTERMEDIATE

        return AIVerdict(
            approved=bool(data.get("approved", False)),
            confidence=float(data.get("confidence", 0.0)),
            category=str(data.get("category", "Other")),
            difficulty=difficulty,
            summary=str(data.get("summary", "")),
            reasoning=str(data.get("reasoning", "")),
        )
