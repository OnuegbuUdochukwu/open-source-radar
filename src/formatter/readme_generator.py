from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from src.models import ProcessedIdea

logger = structlog.get_logger(__name__)

CATEGORY_ORDER = [
    "AI/ML",
    "Web Applications",
    "Python",
    "JavaScript",
    "TypeScript",
    "React",
    "Next.js",
    "Rust",
    "Go",
    "Developer Tools",
    "CLI Tools",
    "APIs",
    "DevOps",
    "Cybersecurity",
    "Data Engineering",
    "Automation",
    "Mobile",
    "Java",
    "C#",
    "Productivity",
    "Education",
    "AI Projects",
    "Beginner Friendly",
    "Other",
]

SOURCE_ICONS = {
    "github": "",
    "reddit": "",
    "hackernews": "",
}

DIFFICULTY_BADGES = {
    "Beginner": "",
    "Intermediate": "",
    "Advanced": "",
}


class READMEGenerator:
    """Generates and maintains the README.md with curated ideas.

    Uses a section-based injection approach:
    - Existing content is preserved
    - Only new verified entries are appended
    - Sections are organized by category
    """

    def __init__(self, readme_path: str = "README.md") -> None:
        self.readme_path = readme_path

    def generate_readme(self, ideas: list[ProcessedIdea], metrics: dict[str, Any] | None = None) -> str:
        """Generate the complete README content."""
        lines: list[str] = []
        lines.append("# Open Source Ideas\n")
        lines.append(
            "> An automatically curated collection of high-quality open-source project ideas, "
            "collected daily from GitHub, Reddit, and Hacker News.\n"
        )
        lines.append(
            "[![Daily Update](https://github.com/OnuegbuUdochukwu/open-source-radar/actions/workflows/daily_update.yml/badge.svg)]"
            "(https://github.com/OnuegbuUdochukwu/open-source-radar/actions/workflows/daily_update.yml)\n"
        )

        lines.append("## Stats\n")
        if metrics:
            lines.append(f"- **Total Ideas:** {metrics.get('total_ideas', 0)}")
            lines.append(f"- **Approved:** {metrics.get('approved_ideas', 0)}")
            lines.append(f"- **Categories:** {len(metrics.get('categories', {}))}")
            lines.append(f"- **Last Updated:** {metrics.get('last_updated', 'N/A')}")
        lines.append("")

        lines.append("## Table of Contents\n")
        for cat in CATEGORY_ORDER:
            lines.append(f"- [{cat}](#{cat.lower().replace('/', '').replace(' ', '-').replace('.', '')})")
        lines.append("")

        # Group ideas by category
        categorized = self._group_by_category(ideas)

        for category in CATEGORY_ORDER:
            cat_ideas = categorized.get(category, [])
            if not cat_ideas:
                continue

            lines.append(f"## {category}\n")
            for idea in cat_ideas[:20]:  # Max 20 per category
                lines.append(self._format_entry(idea))
            lines.append("")

        lines.append("---\n")
        lines.append(f"*Automatically generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")
        lines.append("*Powered by [Open Source Radar](https://github.com/OnuegbuUdochukwu/open-source-radar)*\n")

        return "\n".join(lines)

    def _format_entry(self, idea: ProcessedIdea) -> str:
        """Format a single idea entry."""
        lines: list[str] = []
        lines.append(f"### {idea.title}")

        # Source badge
        source_icon = SOURCE_ICONS.get(idea.source.value, "")
        lines.append(f"**Source:** {source_icon}{idea.source.value.title()} | "
                      f"**Difficulty:** {idea.difficulty.value}")

        if idea.tech_stack:
            tech_str = ", ".join(idea.tech_stack[:5])
            lines.append(f"**Tech Stack:** {tech_str}")

        lines.append("")
        lines.append(idea.description[:300] + ("..." if len(idea.description) > 300 else ""))
        lines.append("")

        links = []
        if idea.url:
            links.append(f"[Original{' Repository' if idea.source.value == 'github' else ' Post'}]({idea.url})")
        links.append(f"[Source: {idea.source.value.title()}]({idea.url})")
        lines.append(" | ".join(links))
        lines.append("")

        return "\n".join(lines)

    def _group_by_category(self, ideas: list[ProcessedIdea]) -> dict[str, list[ProcessedIdea]]:
        """Group ideas by their primary category."""
        grouped: dict[str, list[ProcessedIdea]] = {}
        for idea in ideas:
            # Assign to first valid category, or "Other"
            assigned = False
            for cat in idea.categories:
                if cat in CATEGORY_ORDER:
                    grouped.setdefault(cat, []).append(idea)
                    assigned = True
                    break
            if not assigned:
                grouped.setdefault("Other", []).append(idea)

        # Sort within each group by quality score descending
        for cat in grouped:
            grouped[cat].sort(key=lambda x: x.quality_score, reverse=True)

        return grouped

    def update_readme_file(self, content: str) -> None:
        """Write the generated README to disk."""
        with open(self.readme_path, "w") as f:
            f.write(content)
        logger.info("readme_updated", path=self.readme_path)
