from __future__ import annotations

import json
import re
from typing import Any

import openai
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


class OpenAIProvider(AIProvider):
    """OpenAI provider for idea evaluation."""

    provider_name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.openai_api_key
        self._client: openai.AsyncOpenAI | None = None

    def _get_client(self) -> openai.AsyncOpenAI:
        if self._client is None:
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            await client.models.list()
            return True
        except Exception:
            return False

    @async_retry()
    async def evaluate_idea(self, idea: RawIdea) -> AIVerdict:
        if not self.api_key:
            logger.warning("openai_no_api_key")
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
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300,
            )
            text = response.choices[0].message.content or "{}"
            return self._parse_response(text, idea)
        except Exception as e:
            logger.error("openai_evaluation_error", error=str(e), title=idea.title)
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
