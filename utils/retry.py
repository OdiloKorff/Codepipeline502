"""
Retry utilities for CodePipeline.
"""

import random
import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, cast

import requests

from codepipeline.logging_config import get_logger

F = TypeVar("F", bound=Callable)

logger = get_logger(__name__)

def retry(
    max_retries: int = 5,
    initial_backoff: float = 0.1,
    backoff_factor: float = 2.0,
    jitter: float = 0.2,
    retry_on_statuses: tuple = (429, 502, 503),
) -> Callable[[F], F]:
    """
    Decorator for retrying a function with exponential backoff and jitter.
    Retries on HTTP status codes defined in retry_on_statuses.
    Logs each attempt.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            backoff = initial_backoff
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    status = getattr(e.response, "status_code", None)
                    if status in retry_on_statuses:
                        sleep = backoff * (1 + random.uniform(-jitter, jitter))
                        logger.warning(
                            "Attempt %d failed with status %s; retrying in %.2f seconds",
                            attempt, status, sleep
                        )
                        time.sleep(sleep)
                        backoff *= backoff_factor
                        continue
                    raise
            logger.error("Max retries exceeded (%d)", max_retries)
            raise
        return cast(F, wrapper)
    return decorator
