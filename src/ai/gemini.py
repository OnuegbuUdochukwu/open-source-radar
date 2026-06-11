from __future__ import annotations

import json
import re
from typing import Any

import google.generativeai as genai
import structlog

from src.ai.base import AIProvider
from src.config import settings
from src.models import AIVerdict, DifficultyLevel, RawIdea
from src.utils.retry import async_retry

logger = structlog.get_logger(__name__)

EVALUATION_PROMPT = """You are an expert curator evaluating open-source project ideas.

Analyze this project idea and determine if it should be featured on a curated open-source ideas platform.

Idea Title: {title}
Description: {description}
Source: {source}
Language/Tech: {language}
Stars/Score: {score}
Topics: {topics}

Evaluate on these criteria:
1. Is this a legitimate project idea? (Not a joke, spam, or placeholder)
2. Is it unique and interesting?
3. Is it useful or educational for developers?
4. Is it original (not a common tutorial like "to-do app" or "blog" unless it has a unique twist)?
5. Would developers want to build or contribute to this?

Respond ONLY with a JSON object (no markdown, no code fences):
{{
    "approved": true/false,
    "confidence": 0.0-1.0,
    "category": "Web Development | AI/ML | Developer Tools | CLI Tools | APIs | "
               "Automation | Cybersecurity | Data Engineering | Mobile | DevOps | "
               "Productivity | Education | Other",
    "difficulty": "Beginner | Intermediate | Advanced",
    "summary": "One-sentence summary of the project idea",
    "reasoning": "Brief explanation of the decision (1-2 sentences)"
}}"""


class GeminiProvider(AIProvider):
    """Google Gemini AI provider for idea evaluation."""

    provider_name = "gemini"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self._model = "models/gemini-2.0-flash-001"
        self._initialized = False

    def _initialize(self) -> None:
        if not self._initialized:
            genai.configure(api_key=self.api_key)
            self._initialized = True

    async def health_check(self) -> bool:
        try:
            self._initialize()
            return bool(self.api_key)
        except Exception:
            return False

    @async_retry()
    async def evaluate_idea(self, idea: RawIdea) -> AIVerdict:
        if not self.api_key:
            logger.warning("gemini_no_api_key")
            return AIVerdict(
                approved=False,
                confidence=0.0,
                category="Other",
                difficulty=DifficultyLevel.INTERMEDIATE,
                summary="",
                reasoning="Gemini API key not configured",
            )

        self._initialize()
        model = genai.GenerativeModel(self._model)

        prompt = EVALUATION_PROMPT.format(
            title=idea.title[:500],
            description=idea.description[:1000] if idea.description else "No description available",
            source=idea.source.value,
            language=idea.language or "Not specified",
            score=idea.score,
            topics=", ".join(idea.topics[:10]) if idea.topics else "None",
        )

        try:
            response = await model.generate_content_async(prompt)
            text = response.text.strip()
            return self._parse_response(text, idea)
        except Exception as e:
            logger.error("gemini_evaluation_error", error=str(e), title=idea.title)
            return AIVerdict(
                approved=False,
                confidence=0.0,
                category="Other",
                difficulty=DifficultyLevel.INTERMEDIATE,
                summary="",
                reasoning=f"AI evaluation failed: {str(e)[:200]}",
            )

    def _parse_response(self, text: str, idea: RawIdea) -> AIVerdict:
        # Strip markdown code fences if present
        text = re.sub(r"```(?:json)?\s*", "", text).strip()

        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("gemini_json_parse_failed", text=text[:200])
            return AIVerdict(
                approved=False,
                confidence=0.0,
                category="Other",
                difficulty=DifficultyLevel.INTERMEDIATE,
                summary="",
                reasoning="AI response was not valid JSON",
            )

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
