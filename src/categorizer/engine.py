from __future__ import annotations

import re
from typing import Any

import structlog

from src.models import ProcessedIdea

logger = structlog.get_logger(__name__)

TECHNOLOGY_CATEGORIES: dict[str, list[str]] = {
    "Python": ["python", "django", "flask", "fastapi", "pytorch", "tensorflow",
               "pandas", "numpy", "scikit", "jupyter"],
    "JavaScript": ["javascript", "js", "node", "nodejs", "express", "npm", "yarn",
                   "webpack", "babel", "jquery", "vanilla"],
    "TypeScript": ["typescript", "ts", "deno", "bun", "tsx", "typeorm", "prisma", "nest", "nextjs"],
    "React": ["react", "reactjs", "react-native", "jsx", "hooks", "redux", "nextjs", "gatsby", "remix"],
    "Next.js": ["nextjs", "next.js", "next-js", "nextjs13", "app-router", "server-actions"],
    "Rust": ["rust", "rust-lang", "cargo", "rustc", "wasm", "webassembly"],
    "Go": ["go", "golang", "go-lang", "goroutine", "gin-gonic"],
    "Java": ["java", "spring", "spring-boot", "maven", "gradle", "kotlin", "jvm", "android"],
    "C#": ["csharp", "c-sharp", "c#", "dotnet", ".net", "asp.net", "blazor", "unity"],
    "AI/ML": ["machine-learning", "deep-learning", "ai", "artificial-intelligence",
              "ml", "nlp", "llm", "neural", "transformer", "gpt", "pytorch",
              "tensorflow", "keras", "scikit-learn", "xgboost"],
    "Mobile": ["android", "ios", "flutter", "swift", "react-native",
               "kotlin", "mobile", "app", "swiftui", "uikit"],
    "DevOps": ["docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins",
               "ci/cd", "github-actions", "gitops", "helm", "prometheus", "grafana"],
    "Cybersecurity": ["security", "cybersecurity", "encryption", "auth", "oauth",
                      "jwt", "vulnerability", "penetration", "malware", "firewall"],
}

TOPIC_CATEGORIES: dict[str, list[str]] = {
    "Web Applications": ["web", "webapp", "website", "dashboard", "frontend",
                         "backend", "fullstack", "api", "rest", "graphql", "saas", "spa"],
    "CLI Tools": ["cli", "command-line", "terminal", "shell", "console", "tui", "bash"],
    "AI Projects": ["ai", "machine-learning", "deep-learning", "llm", "gpt", "chatbot",
                    "nlp", "computer-vision", "recommendation"],
    "Developer Tools": ["developer-tools", "devtools", "ide", "editor", "debugger",
                        "profiler", "linter", "formatter", "compiler", "framework"],
    "APIs": ["api", "rest", "graphql", "grpc", "websocket", "sdk", "integration", "webhook"],
    "Automation": ["automation", "workflow", "pipeline", "bot", "scraper", "scheduler", "cron"],
    "Cybersecurity": ["security", "encryption", "auth", "privacy", "penetration-testing", "vulnerability"],
    "Data Engineering": ["data", "etl", "pipeline", "analytics", "database",
                         "big-data", "streaming", "lake", "warehouse"],
    "Productivity": ["productivity", "todo", "note", "organizer", "planner", "tracker", "calendar", "habit"],
    "Education": ["education", "learning", "tutorial", "course", "interactive", "teaching", "documentation"],
}

DIFFICULTY_KEYWORDS: dict[str, list[str]] = {
    "Beginner": ["beginner", "starter", "simple", "easy", "basic", "tutorial",
                 "getting-started", "hello-world", "learning", "introduction",
                 "first-project", "newbie"],
    "Advanced": ["advanced", "complex", "distributed", "high-performance", "scalable",
                 "real-time", "production", "enterprise", "kernel", "compiler",
                 "database-engine", "game-engine", "operating-system", "deep-learning", "llm"],
}


class CategorizationEngine:
    """Multi-dimensional categorization engine.

    Assigns technology, topic, and difficulty categories to each idea
    based on keyword matching on title, description, language, and topics.
    """

    def categorize(self, idea: ProcessedIdea) -> ProcessedIdea:
        """Run all categorization strategies on an idea."""
        tech_cats = self._match_technology(idea)
        topic_cats = self._match_topics(idea)
        difficulty = self._infer_difficulty(idea)
        tech_stack = self._extract_tech_stack(idea)

        all_categories = list(set(tech_cats + topic_cats))
        if not all_categories:
            all_categories = ["Other"]

        idea.categories = all_categories
        idea.difficulty = difficulty
        idea.tech_stack = tech_stack

        logger.info(
            "idea_categorized",
            title=idea.title,
            categories=all_categories,
            difficulty=difficulty.value,
            tech_stack=tech_stack,
        )

        return idea

    def _match_technology(self, idea: ProcessedIdea) -> list[str]:
        """Match technology categories based on language, topics, and content."""
        matches: list[str] = []
        search_text = self._build_search_text(idea).lower()

        for category, keywords in TECHNOLOGY_CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in search_text:
                    matches.append(category)
                    break

        return matches

    def _match_topics(self, idea: ProcessedIdea) -> list[str]:
        """Match topic categories based on content analysis."""
        matches: list[str] = []
        search_text = self._build_search_text(idea).lower()

        for category, keywords in TOPIC_CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in search_text:
                    matches.append(category)
                    break

        return matches

    def _infer_difficulty(self, idea: ProcessedIdea) -> Any:
        """Infer difficulty from content."""
        from src.models import DifficultyLevel

        search_text = self._build_search_text(idea).lower()

        # Check advanced first (more specific)
        for keyword in DIFFICULTY_KEYWORDS["Advanced"]:
            if keyword.lower() in search_text:
                return DifficultyLevel.ADVANCED

        # Check beginner
        for keyword in DIFFICULTY_KEYWORDS["Beginner"]:
            if keyword.lower() in search_text:
                return DifficultyLevel.BEGINNER

        # Default: use the AI-provided difficulty (already set) or intermediate
        return idea.difficulty

    def _extract_tech_stack(self, idea: ProcessedIdea) -> list[str]:
        """Extract technology stack from the idea."""
        stack: list[str] = []

        if idea.language and idea.language.lower() != "unknown":
            stack.append(idea.language)

        for topic in idea.topics:
            if topic not in stack:
                stack.append(topic)

        # Extract from description
        if idea.description:
            tech_patterns = [
                r"\b(Python|JavaScript|TypeScript|Rust|Go|Java|C#|C\+\+|Kotlin|Swift|Ruby|PHP|Scala)\b",
                r"\b(React|Vue|Angular|Svelte|Django|Flask|FastAPI|Spring|Express|Next\.?js|Nuxt)\b",
                r"\b(Docker|Kubernetes|Terraform|Ansible|Jenkins)\b",
                r"\b(PostgreSQL|MySQL|SQLite|MongoDB|Redis|Elasticsearch)\b",
                r"\b(AWS|GCP|Azure|Firebase|Supabase)\b",
            ]
            for pattern in tech_patterns:
                found = re.findall(pattern, idea.description, re.IGNORECASE)
                for tech in found:
                    normalized = tech.replace(".", "").strip()
                    if normalized and normalized not in stack:
                        stack.append(normalized)

        return stack[:10]  # Limit to 10 items

    def _build_search_text(self, idea: ProcessedIdea) -> str:
        """Build a combined search text from all relevant fields."""
        parts = [
            idea.title,
            idea.description,
            idea.language,
            " ".join(idea.topics),
            " ".join(idea.categories),
        ]
        return " ".join(parts)
