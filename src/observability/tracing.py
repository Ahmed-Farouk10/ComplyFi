from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

_resource = Resource.create({SERVICE_NAME: "fintech-compliance-platform"})
_provider = TracerProvider(resource=_resource)
_processor = BatchSpanProcessor(ConsoleSpanExporter())
_provider.add_span_processor(_processor)
trace.set_tracer_provider(_provider)

_tracer = trace.get_tracer(__name__)


def setup_tracing(service_name: str = "fintech-compliance-platform") -> None:
    global _tracer
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)


@asynccontextmanager
async def trace_compliance_span(
    agent_name: str,
    step: str | None = None,
    query: str | None = None,
    case_id: str | None = None,
):
    span_name = f"compliance.{agent_name}"
    if step:
        span_name = f"compliance.{agent_name}.{step}"

    span = _tracer.start_span(span_name)
    span.set_attribute("compliance.agent", agent_name)
    if step:
        span.set_attribute("compliance.step", step)
    if case_id:
        span.set_attribute("compliance.case_id", case_id)
    if query:
        span.set_attribute("compliance.query_preview", query[:200] if len(query) > 200 else query)

    start = time.perf_counter()
    result_holder: dict[str, Any] = {}
    try:
        yield result_holder
        duration = time.perf_counter() - start
        span.set_attribute("compliance.duration_ms", round(duration * 1000))
        tokens = result_holder.get("tokens", {})
        span.set_attribute("compliance.tokens.prompt", tokens.get("prompt", 0))
        span.set_attribute("compliance.tokens.completion", tokens.get("completion", 0))
        span.set_attribute("compliance.tokens.total", tokens.get("prompt", 0) + tokens.get("completion", 0))
        span.set_status(trace.Status(trace.StatusCode.OK))
    except Exception as exc:
        duration = time.perf_counter() - start
        span.set_attribute("compliance.duration_ms", round(duration * 1000))
        span.set_attribute("compliance.error", str(exc))
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
        raise
    finally:
        span.end()
