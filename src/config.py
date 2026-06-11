from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AI Providers
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    hf_token: str = ""

    # Hugging Face model (free serverless inference)
    # Best free models for structured JSON output:
    #   Qwen/Qwen2.5-7B-Instruct  (best JSON/instruction following)
    #   meta-llama/Meta-Llama-3.1-8B-Instruct  (strong all-rounder)
    #   mistralai/Mistral-7B-Instruct-v0.3  (fast, lighter)
    hf_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # Preferred AI provider
    ai_provider: Literal["gemini", "openai", "anthropic", "huggingface"] = "huggingface"

    # GitHub
    github_token: str = ""

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "open-source-radar/1.0"

    # Pipeline
    log_level: str = "INFO"
    dry_run: bool = False
    max_ideas_per_source: int = 100
    ai_evaluation_enabled: bool = True

    # Paths
    data_dir: str = "data"
    logs_dir: str = "logs"
    reports_dir: str = "reports"

    # Database
    database_path: str = "data/ideas.db"

    # Monitoring thresholds
    warning_readme_size_kb: int = 500
    warning_total_ideas: int = 1_500
    critical_readme_size_kb: int = 1_000
    critical_total_ideas: int = 3_000

    # Quality thresholds
    github_stars_viral: int = 500
    reddit_upvotes_viral: int = 200
    hackernews_score_viral: int = 150
    github_stars_minimum: int = 20
    reddit_upvotes_minimum: int = 10
    hackernews_score_minimum: int = 15

    # Semantic similarity threshold (0-1)
    similarity_threshold: float = 0.85

    # Retry
    max_retries: int = 3
    retry_base_delay: float = 2.0

    # Rate limiting
    requests_per_second: float = 2.0

    # GitHub repo for publishing
    github_repo: str = "OnuegbuUdochukwu/open-source-radar"
    github_branch: str = "main"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def logs_path(self) -> Path:
        return Path(self.logs_dir)

    @property
    def reports_path(self) -> Path:
        return Path(self.reports_dir)

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)

    @property
    def ideas_json_path(self) -> Path:
        return Path(self.data_dir) / "ideas.json"

    @property
    def metrics_json_path(self) -> Path:
        return Path(self.data_dir) / "metrics.json"


settings = Settings()
