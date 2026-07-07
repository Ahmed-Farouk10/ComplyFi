from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request

from src.gateway.python.models import (
    ComplianceVerifyRequest,
    ComplianceVerifyResponse,
    ComplianceScreenRequest,
    ComplianceScreenResponse,
    AuditTrailResponse,
)
from src.agents.workflows.sequential import run_sequential
from src.agents.workflows.concurrent import run_concurrent
from src.agents.workflows.handoff import run_handoff
from src.agents.middleware.guardrails import Guardrails
from src.agents.middleware.retry import retry_with_backoff
from src.observability.metrics import (
    record_compliance_call,
    get_compliance_metrics,
    reset_compliance_metrics,
)

router = APIRouter()
_guard = Guardrails()

AUDIT_TRAIL: list[dict[str, Any]] = []


def _get_client(request: Request):
    return request.app.state.openai_client


def _get_model(request: Request) -> str:
    return request.app.state.model


async def _run_compliance_workflow(
    client,
    model: str,
    query: str,
    workflow_type: str,
) -> dict[str, Any]:
    if workflow_type == "sequential":
        return await run_sequential(client, model, query)
    elif workflow_type == "concurrent":
        return await run_concurrent(client, model, query)
    elif workflow_type == "handoff":
        return await run_handoff(client, model, query)
    else:
        return {"error": f"Unknown compliance workflow type: {workflow_type}", "trace": [], "result": None}


@router.post("/compliance/verify", response_model=ComplianceVerifyResponse)
async def compliance_verify(payload: ComplianceVerifyRequest, request: Request) -> ComplianceVerifyResponse:
    ok, violation = _guard.check_input(payload.query)
    if not ok:
        return ComplianceVerifyResponse(
            case_id=payload.case_id,
            result=None,
            status="REJECTED",
            guardrail_violations=[violation] if violation else [],
        )

    sanctions_ok, sanctions_hits = _guard.check_sanctions(payload.query)
    if not sanctions_ok:
        return ComplianceVerifyResponse(
            case_id=payload.case_id,
            result=None,
            status="ESCALATED",
            sanctions_hits=sanctions_hits,
        )

    client = _get_client(request)
    model = _get_model(request)

    start = time.perf_counter()
    try:
        result = await retry_with_backoff(
            _run_compliance_workflow,
            client,
            model,
            payload.query,
            payload.workflow_type,
            idempotency_key=payload.case_id or f"verify_{int(time.time() * 1000)}",
        )
    except Exception as exc:
        result = {"error": str(exc), "trace": [], "result": None}

    elapsed_ms = round((time.perf_counter() - start) * 1000)
    total_tokens = {"prompt": 0, "completion": 0}
    for step in result.get("trace", []):
        tokens = step.get("tokens", {})
        total_tokens["prompt"] += tokens.get("prompt", 0)
        total_tokens["completion"] += tokens.get("completion", 0)

    record_compliance_call(payload.workflow_type, elapsed_ms, total_tokens)

    agent_output = result.get("result", "")
    if agent_output:
        ok_out, violations = _guard.check_output(agent_output)
        if not ok_out:
            AUDIT_TRAIL.append({
                "case_id": payload.case_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "workflow": "verify",
                "status": "FLAGGED",
                "violations": violations,
            })
            return ComplianceVerifyResponse(
                case_id=payload.case_id,
                result=agent_output,
                status="FLAGGED",
                guardrail_violations=violations,
            )

    AUDIT_TRAIL.append({
        "case_id": payload.case_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workflow": "verify",
        "sub_workflow": payload.workflow_type,
        "status": "COMPLETED",
        "duration_ms": elapsed_ms,
        "token_usage": total_tokens,
        "trace_length": len(result.get("trace", [])),
    })

    return ComplianceVerifyResponse(
        case_id=payload.case_id,
        result=result.get("result"),
        status="COMPLETED",
        trace=result.get("trace", []),
    )


@router.post("/compliance/screen", response_model=ComplianceScreenResponse)
async def compliance_screen(payload: ComplianceScreenRequest, request: Request) -> ComplianceScreenResponse:
    ok, violation = _guard.check_input(payload.entity_query)
    if not ok:
        return ComplianceScreenResponse(
            entity_name=payload.entity_name,
            result=None,
            status="REJECTED",
            guardrail_violations=[violation] if violation else [],
        )

    client = _get_client(request)
    model = _get_model(request)

    start = time.perf_counter()
    try:
        result = await retry_with_backoff(
            run_concurrent,
            client,
            model,
            payload.entity_query,
            idempotency_key=f"screen_{payload.entity_name}_{int(time.time() * 1000)}",
        )
    except Exception as exc:
        result = {"error": str(exc), "trace": [], "result": None}

    elapsed_ms = round((time.perf_counter() - start) * 1000)
    total_tokens = {"prompt": 0, "completion": 0}
    for step in result.get("trace", []):
        tokens = step.get("tokens", {})
        total_tokens["prompt"] += tokens.get("prompt", 0)
        total_tokens["completion"] += tokens.get("completion", 0)

    record_compliance_call("screen", elapsed_ms, total_tokens)

    agent_output = result.get("result", "")
    if agent_output:
        ok_out, violations = _guard.check_output(agent_output)
        if not ok_out:
            return ComplianceScreenResponse(
                entity_name=payload.entity_name,
                result=agent_output,
                status="FLAGGED",
                guardrail_violations=violations,
            )

    AUDIT_TRAIL.append({
        "entity_name": payload.entity_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workflow": "screen",
        "status": "COMPLETED",
        "duration_ms": elapsed_ms,
        "token_usage": total_tokens,
    })

    return ComplianceScreenResponse(
        entity_name=payload.entity_name,
        result=result.get("result"),
        status="COMPLETED",
        screening_results=result.get("trace", []),
    )


@router.get("/compliance/audit-trail", response_model=list[AuditTrailResponse])
async def get_audit_trail(limit: int = 50, case_id: str | None = None) -> list[AuditTrailResponse]:
    entries = AUDIT_TRAIL
    if case_id:
        entries = [e for e in entries if e.get("case_id") == case_id]
    return [AuditTrailResponse(**e) for e in entries[-limit:]]


@router.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "fintech-compliance-gateway",
    }
