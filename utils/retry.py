"""Retry decorator with exponential backoff, driven by config.settings."""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, TypeVar

from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Create a decorator that retries a function with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including the first one).
        delay: Initial delay in seconds before the first retry.
        backoff: Multiplier applied to the delay after each failed attempt.
        exceptions: Tuple of exception types that should trigger a retry.
            Any other exception propagates immediately.

    Returns:
        A decorator that wraps a function with retry behaviour.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # noqa: BLE001 - intentional broad catch
                    last_exc = exc
                    logger.warning(
                        "Attempt %d/%d for %s failed: %s",
                        attempt,
                        max_attempts,
                        func.__name__,
                        exc,
                    )
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            logger.error(
                "All %d attempts for %s failed.", max_attempts, func.__name__, exc_info=last_exc
            )
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
