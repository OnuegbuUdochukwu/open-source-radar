from __future__ import annotations

import json
import re
from typing import Any

import structlog
from huggingface_hub import InferenceClient

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

Respond ONLY with a valid JSON object. Do NOT wrap in markdown code fences, do NOT add any other text.

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


class HuggingFaceProvider(AIProvider):
    """Hugging Face free serverless inference provider.

    Uses the Hugging Face Serverless Inference API with free open-weight models.
    Requires only a free HF token (no credit card) — sign up at huggingface.co.

    Default model: Mistral-7B-Instruct-v0.3 (7B params, runs free on HF infra).
    Falls back gracefully on rate limits and outages.
    """

    provider_name = "huggingface"

    def __init__(self, token: str | None = None, model: str | None = None) -> None:
        self.token = token or settings.hf_token
        self.model = model or settings.hf_model
        self._client: InferenceClient | None = None

    def _get_client(self) -> InferenceClient:
        if self._client is None:
            self._client = InferenceClient(model=self.model, token=self.token)
        return self._client

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            response = client.chat_completion(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(response and response.choices)
        except Exception as e:
            logger.warning("huggingface_health_check_failed", error=str(e))
            return False

    @async_retry()
    async def evaluate_idea(self, idea: RawIdea) -> AIVerdict:
        if not self.token:
            logger.warning("huggingface_no_token")
            return AIVerdict(
                approved=False,
                confidence=0.0,
                category="Other",
                difficulty=DifficultyLevel.INTERMEDIATE,
                summary="",
                reasoning="HF_TOKEN not configured — get a free token at huggingface.co/settings/tokens",
            )

        client = self._get_client()
        prompt = EVALUATION_PROMPT.format(
            title=idea.title[:500],
            description=idea.description[:1000] if idea.description else "No description available",
            source=idea.source.value,
            language=idea.language or "Not specified",
            score=idea.score,
            topics=", ".join(idea.topics[:10]) if idea.topics else "None",
        )

        try:
            response = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1,
            )
            text = response.choices[0].message.content or ""
            return self._parse_response(text, idea)
        except Exception as e:
            logger.error("huggingface_evaluation_error", error=str(e), title=idea.title)

            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                return AIVerdict(
                    approved=False,
                    confidence=0.0,
                    category="Other",
                    difficulty=DifficultyLevel.INTERMEDIATE,
                    summary="",
                    reasoning="Hugging Face rate limit exceeded — try again later",
                )
            if "authorization" in error_str or "401" in error_str or "token" in error_str:
                return AIVerdict(
                    approved=False,
                    confidence=0.0,
                    category="Other",
                    difficulty=DifficultyLevel.INTERMEDIATE,
                    summary="",
                    reasoning="Invalid HF_TOKEN — get a free token at huggingface.co/settings/tokens",
                )

            return AIVerdict(
                approved=False,
                confidence=0.0,
                category="Other",
                difficulty=DifficultyLevel.INTERMEDIATE,
                summary="",
                reasoning=f"Hugging Face inference failed: {str(e)[:200]}",
            )

    def _parse_response(self, text: str, idea: RawIdea) -> AIVerdict:
        """Parse JSON from LLM response, handling common formatting issues."""
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        text = re.sub(r"\s*```", "", text).strip()

        # Try to extract JSON object
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            # Attempt to find JSON within the response
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    logger.warning("huggingface_json_parse_failed", text=text[:200])
                    return AIVerdict(
                        approved=False,
                        confidence=0.0,
                        category="Other",
                        difficulty=DifficultyLevel.INTERMEDIATE,
                        summary="",
                        reasoning="AI response was not valid JSON",
                    )
            else:
                logger.warning("huggingface_no_json_found", text=text[:200])
                return AIVerdict(
                    approved=False,
                    confidence=0.0,
                    category="Other",
                    difficulty=DifficultyLevel.INTERMEDIATE,
                    summary="",
                    reasoning="AI response contained no JSON",
                )

        difficulty_str = data.get("difficulty", "Intermediate")
        try:
            difficulty = DifficultyLevel(difficulty_str)
        except ValueError:
            difficulty = DifficultyLevel.INTERMEDIATE

        confidence = float(data.get("confidence", 0.0))
        approved = bool(data.get("approved", False))

        return AIVerdict(
            approved=approved,
            confidence=min(confidence, 1.0),
            category=str(data.get("category", "Other")),
            difficulty=difficulty,
            summary=str(data.get("summary", "")),
            reasoning=str(data.get("reasoning", "")),
        )
