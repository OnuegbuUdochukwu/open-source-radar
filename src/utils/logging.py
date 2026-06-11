from __future__ import annotations

import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer

from src.config import settings


def configure_logging() -> None:
    """Configure structured logging based on environment."""
    if settings.log_level == "JSON":
        renderer = JSONRenderer()
    else:
        renderer = ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        context_class=dict,
        cache_logger_on_first_use=True,
    )
