from __future__ import annotations

import functools
import time
import uuid
from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def generate_audit_id() -> str:
    return f"audit-{uuid.uuid4().hex[:12]}"


def log_agent_call(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        call_id = kwargs.get("call_id", f"call_{int(time.time() * 1000)}")
        agent_name = kwargs.get("agent_name", func.__name__)
        compliance_case_id = kwargs.get("case_id", generate_audit_id())
        operator_id = kwargs.get("operator_id", "system")

        logger.info(
            "compliance_agent_call_start",
            audit_id=call_id,
            case_id=compliance_case_id,
            agent=agent_name,
            operator_id=operator_id,
            arg_count=len(args),
            kwarg_keys=list(kwargs.keys()),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.info(
                "compliance_agent_call_success",
                audit_id=call_id,
                case_id=compliance_case_id,
                agent=agent_name,
                duration_ms=round(elapsed * 1000),
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                disposition="COMPLETED",
            )
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error(
                "compliance_agent_call_failure",
                audit_id=call_id,
                case_id=compliance_case_id,
                agent=agent_name,
                duration_ms=round(elapsed * 1000),
                error=str(exc),
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                disposition="FAILED",
            )
            raise

    return wrapper
