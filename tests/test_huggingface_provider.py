from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ai.huggingface import HuggingFaceProvider
from src.models import DifficultyLevel, RawIdea, SourceType


@pytest.fixture
def sample_idea():
    return RawIdea(
        id="test-hf-1",
        source=SourceType.GITHUB,
        source_id="hf-test-1",
        title="AI-Powered Code Review Tool",
        description="A tool that uses machine learning to automatically review pull requests",
        url="https://github.com/test/code-reviewer",
        author="devuser",
        score=150,
        stars=150,
        forks=30,
        language="Python",
        topics=["ai", "code-review", "machine-learning"],
        comments=0,
    )


@pytest.fixture
def hf_provider():
    return HuggingFaceProvider(token="fake-token", model="mistralai/Mistral-7B-Instruct-v0.3")


class TestHuggingFaceProvider:
    def test_parse_valid_json(self, hf_provider, sample_idea):
        response_text = (
            '{"approved": true, "confidence": 0.92, "category": "Developer Tools", '
            '"difficulty": "Intermediate", "summary": "An AI code review tool", '
            '"reasoning": "Legitimate and useful project"}'
        )
        verdict = hf_provider._parse_response(response_text, sample_idea)
        assert verdict.approved is True
        assert verdict.confidence == 0.92
        assert verdict.category == "Developer Tools"
        assert verdict.difficulty == DifficultyLevel.INTERMEDIATE

    def test_parse_json_with_code_fences(self, hf_provider, sample_idea):
        response_text = (
            "```json\n{\"approved\": true, \"confidence\": 0.85, \"category\": \"Web Development\", "
            "\"difficulty\": \"Beginner\", \"summary\": \"A web project\", "
            "\"reasoning\": \"Good for learning\"}\n```"
        )
        verdict = hf_provider._parse_response(response_text, sample_idea)
        assert verdict.approved is True
        assert verdict.confidence == 0.85
        assert verdict.difficulty == DifficultyLevel.BEGINNER

    def test_parse_rejected_idea(self, hf_provider, sample_idea):
        response_text = (
            '{"approved": false, "confidence": 0.3, "category": "Other", '
            '"difficulty": "Intermediate", "summary": "", "reasoning": "Spam detected"}'
        )
        verdict = hf_provider._parse_response(response_text, sample_idea)
        assert verdict.approved is False
        assert verdict.confidence == 0.3

    def test_parse_invalid_json(self, hf_provider, sample_idea):
        response_text = "This is not JSON at all"
        verdict = hf_provider._parse_response(response_text, sample_idea)
        assert verdict.approved is False
        assert verdict.confidence == 0.0
        assert verdict.reasoning != ""

    def test_parse_json_embedded_in_text(self, hf_provider, sample_idea):
        response_text = (
            "Here is my analysis:\n{\"approved\": true, \"confidence\": 0.75, "
            "\"category\": \"CLI Tools\", \"difficulty\": \"Advanced\", "
            "\"summary\": \"A CLI tool\", \"reasoning\": \"Interesting project\"}\nHope this helps!"
        )
        verdict = hf_provider._parse_response(response_text, sample_idea)
        assert verdict.approved is True
        assert verdict.category == "CLI Tools"

    @pytest.mark.asyncio
    async def test_no_token_returns_early(self, sample_idea):
        provider = HuggingFaceProvider(token="")
        verdict = await provider.evaluate_idea(sample_idea)
        assert verdict.approved is False
        assert "HF_TOKEN" in verdict.reasoning

    @pytest.mark.asyncio
    async def test_health_check_no_token(self):
        provider = HuggingFaceProvider(token="")
        result = await provider.health_check()
        assert result is False

    def test_parse_difficulty_fallback(self, hf_provider, sample_idea):
        response_text = (
            '{"approved": true, "confidence": 0.8, "category": "AI/ML", '
            '"difficulty": "unknown", "summary": "test", "reasoning": "test"}'
        )
        verdict = hf_provider._parse_response(response_text, sample_idea)
        assert verdict.difficulty == DifficultyLevel.INTERMEDIATE  # fallback

    def test_parse_confidence_capped(self, hf_provider, sample_idea):
        response_text = (
            '{"approved": true, "confidence": 1.5, "category": "Web", '
            '"difficulty": "Intermediate", "summary": "test", "reasoning": "test"}'
        )
        verdict = hf_provider._parse_response(response_text, sample_idea)
        assert verdict.confidence <= 1.0

    @pytest.mark.asyncio
    @patch("src.ai.huggingface.InferenceClient")
    async def test_evaluate_idea_success(self, mock_client_cls, hf_provider, sample_idea):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '{"approved": true, "confidence": 0.9, "category": "Developer Tools", '
            '"difficulty": "Intermediate", "summary": "A code review tool", "reasoning": "Good project"}'
        )
        mock_client.chat_completion.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = await hf_provider.evaluate_idea(sample_idea)
        assert result.approved is True
        assert result.confidence == 0.9
        mock_client.chat_completion.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.ai.huggingface.InferenceClient")
    async def test_evaluate_idea_http_error(self, mock_client_cls, hf_provider, sample_idea):
        mock_client = MagicMock()
        mock_client.chat_completion.side_effect = Exception("429 rate limit exceeded")
        mock_client_cls.return_value = mock_client

        result = await hf_provider.evaluate_idea(sample_idea)
        assert result.approved is False
