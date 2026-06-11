from __future__ import annotations

import asyncio
import functools
import inspect
import time
from collections.abc import AsyncIterator, Callable
from typing import Any, TypeVar

import structlog

from src.config import settings

F = TypeVar("F", bound=Callable[..., Any])
logger = structlog.get_logger(__name__)


def retry(
    max_retries: int | None = None,
    base_delay: float | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries a function on failure with exponential backoff."""
    max_retries = max_retries if max_retries is not None else settings.max_retries
    base_delay = base_delay if base_delay is not None else settings.retry_base_delay

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            "retry_attempt",
                            func=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=delay,
                            error=str(e),
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "retry_exhausted",
                            func=func.__name__,
                            error=str(e),
                        )
            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


def async_retry(
    max_retries: int | None = None,
    base_delay: float | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries an async function on failure with exponential backoff.

    Handles both regular async functions and async generators.
    """
    max_retries = max_retries if max_retries is not None else settings.max_retries
    base_delay = base_delay if base_delay is not None else settings.retry_base_delay

    def decorator(func: F) -> F:
        if inspect.isasyncgenfunction(func):
            @functools.wraps(func)
            async def async_gen_wrapper(
                *args: Any, **kwargs: Any
            ) -> AsyncIterator[Any]:
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        async for item in func(*args, **kwargs):
                            yield item
                        return
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                "async_gen_retry_attempt",
                                func=func.__name__,
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                delay=delay,
                                error=str(e),
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.error(
                                "async_gen_retry_exhausted",
                                func=func.__name__,
                                error=str(e),
                            )
                raise last_exception  # type: ignore

            return async_gen_wrapper  # type: ignore

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            "async_retry_attempt",
                            func=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=delay,
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "async_retry_exhausted",
                            func=func.__name__,
                            error=str(e),
                        )
            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator
