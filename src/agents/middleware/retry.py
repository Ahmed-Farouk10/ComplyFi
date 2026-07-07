from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.0


def _is_retryable(exception: Exception) -> bool:
    status = getattr(exception, "status_code", None)
    if status is not None and status in RETRYABLE_STATUSES:
        return True
    http_status = getattr(exception, "http_status", None)
    if http_status is not None and http_status in RETRYABLE_STATUSES:
        return True
    if hasattr(exception, "response") and exception.response is not None:
        resp_status = getattr(exception.response, "status_code", None)
        if resp_status in RETRYABLE_STATUSES:
            return True
    if isinstance(exception, (asyncio.TimeoutError, ConnectionError)):
        return True
    return False


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    idempotency_key: str | None = None,
    **kwargs: Any,
) -> Any:
    """
    Retry with exponential backoff for transient failures.

    Financial transaction idempotency: If an ``idempotency_key`` is provided,
    the caller should pass a unique key per logical transaction. On retry,
    the downstream system can detect duplicate requests by this key and avoid
    double-processing (e.g., duplicate sanctions checks or report submissions).

    Idempotency key format recommendation: ``{case_id}-{workflow_type}-{nonce}``
    """
    last_exception: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if idempotency_key:
                kwargs["idempotency_key"] = idempotency_key
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exception = exc
            if attempt >= max_retries or not _is_retryable(exc):
                logger.error(
                    "compliance_retry_exhausted",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    idempotency_key=idempotency_key,
                    error=str(exc),
                )
                raise

            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(
                "compliance_retry_attempt",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=round(delay, 2),
                idempotency_key=idempotency_key,
                error=str(exc),
            )
            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
