from __future__ import annotations

import time
from typing import Any

from openai import AsyncOpenAI

SPECIALISTS: dict[str, dict[str, str]] = {
    "auto_approve": {
        "name": "auto_approve",
        "description": "Handles low-risk compliance verifications that pass all screening checks with no flags.",
        "system_prompt": (
            "You are an Auto-Approval agent for a fintech compliance platform. "
            "The subject has passed all KYC, AML, fraud, and sanctions checks with no flags. "
            "Generate an approval notice with the compliance case ID, verified identity summary, "
            "screening pass confirmation, and any standard onboarding conditions. "
            "Include notes for SOC 2 audit trail completeness."
        ),
    },
    "manual_review": {
        "name": "manual_review",
        "description": "Handles medium-risk cases that have minor flags requiring human analyst review.",
        "system_prompt": (
            "You are a Manual Review agent for a fintech compliance platform. "
            "The subject has one or more minor flags (e.g., slight name mismatch, medium-risk jurisdiction, "
            "outdated adverse media). Queue this case for a human compliance analyst review. "
            "Summarize the specific flags, provide a checklist for the analyst, and set a review SLA (24 hours). "
            "Include the evidence trail for SOC 2 audit readiness."
        ),
    },
    "compliance_officer_escalation": {
        "name": "compliance_officer_escalation",
        "description": "Handles high-risk cases with sanctions matches, fraud indicators, or missing critical verification.",
        "system_prompt": (
            "You are a Compliance Officer Escalation agent for a fintech compliance platform. "
            "The subject has been flagged as HIGH RISK due to sanctions list matches, confirmed fraud indicators, "
            "or critical identity verification failures. Escalate immediately to a senior compliance officer. "
            "Attach the full risk dossier, freeze any pending transactions, and request an urgent review. "
            "Document all findings per SOC 2 and PCI-DSS incident response requirements."
        ),
    },
}

ROUTER_PROMPT = """You are a compliance risk router agent. Given the results of a fintech compliance screening,
determine the risk level and routing action. Respond ONLY with the specialist name:
auto_approve, manual_review, or compliance_officer_escalation.

Risk levels:
- auto_approve: All checks passed cleanly, no flags, low-risk profile, standard jurisdiction
- manual_review: Minor flags found, medium-risk jurisdiction, outdated or unclear adverse media, slight document discrepancies
- compliance_officer_escalation: Sanctions list match, confirmed fraud indicators, PEP designation, high-risk jurisdiction, critical identity verification failure

Screening Results: {query}
Risk Disposition:"""


async def run_handoff(
    client: AsyncOpenAI,
    model: str,
    query: str,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []

    router_start = time.perf_counter()
    try:
        router_response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
            temperature=0.0,
            max_tokens=20,
        )
        specialist_name = (router_response.choices[0].message.content or "").strip().lower()
        router_usage = router_response.usage
        router_duration = time.perf_counter() - router_start
        trace.append({
            "agent": "risk_router",
            "step": "routing",
            "decision": specialist_name,
            "tokens": {
                "prompt": router_usage.prompt_tokens if router_usage else 0,
                "completion": router_usage.completion_tokens if router_usage else 0,
            },
            "duration_ms": round(router_duration * 1000),
        })
    except Exception as exc:
        trace.append({
            "agent": "risk_router",
            "step": "routing",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - router_start) * 1000),
        })
        return {"result": None, "trace": trace, "error": f"Risk router failed: {exc}"}

    specialist = SPECIALISTS.get(specialist_name, SPECIALISTS["manual_review"])
    specialist_start = time.perf_counter()
    try:
        specialist_response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": specialist["system_prompt"]},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
        )
        specialist_output = specialist_response.choices[0].message.content or ""
        specialist_usage = specialist_response.usage
        specialist_duration = time.perf_counter() - specialist_start
        trace.append({
            "agent": specialist["name"],
            "step": "execution",
            "output": specialist_output,
            "tokens": {
                "prompt": specialist_usage.prompt_tokens if specialist_usage else 0,
                "completion": specialist_usage.completion_tokens if specialist_usage else 0,
            },
            "duration_ms": round(specialist_duration * 1000),
        })
    except Exception as exc:
        trace.append({
            "agent": specialist["name"],
            "step": "execution",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - specialist_start) * 1000),
        })
        return {"result": None, "trace": trace, "error": f"Specialist failed: {exc}"}

    return {"result": specialist_output, "trace": trace}
