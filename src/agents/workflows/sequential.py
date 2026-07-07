from __future__ import annotations

import asyncio
import time
from typing import Any

from openai import AsyncOpenAI


async def run_sequential(
    client: AsyncOpenAI,
    model: str,
    query: str,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    agents = [
        "identity_verification",
        "aml_screening",
        "risk_assessment",
        "report_generation",
    ]
    current_input = query

    for step_idx, agent_name in enumerate(agents):
        step_start = time.perf_counter()
        system_prompt = _prompt_for_agent(agent_name, step_idx)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_input},
                ],
                temperature=0.3,
            )
            output = response.choices[0].message.content or ""
            usage = response.usage
            step_duration = time.perf_counter() - step_start
            trace.append({
                "agent": agent_name,
                "step": step_idx,
                "input": current_input,
                "output": output,
                "tokens": {
                    "prompt": usage.prompt_tokens if usage else 0,
                    "completion": usage.completion_tokens if usage else 0,
                },
                "duration_ms": round(step_duration * 1000),
            })
            current_input = output
        except Exception as exc:
            trace.append({
                "agent": agent_name,
                "step": step_idx,
                "error": str(exc),
                "duration_ms": round((time.perf_counter() - step_start) * 1000),
            })
            return {"result": None, "trace": trace, "error": str(exc)}

    return {"result": current_input, "trace": trace}


def _prompt_for_agent(name: str, step: int) -> str:
    prompts = {
        "identity_verification": (
            "You are an Identity Verification agent for a fintech compliance platform. "
            "Verify the customer's identity against provided documents (e.g., passport, driver's license, national ID). "
            "Check document authenticity, expiration dates, name matching, and facial biometrics if available. "
            "Flag any discrepancies or signs of forgery. Output structured verification results."
        ),
        "aml_screening": (
            "You are an AML (Anti-Money Laundering) Screening agent. "
            "Screen the subject against global sanctions lists (OFAC, UN, EU, HMT), PEP (Politically Exposed Person) databases, "
            "adverse media sources, and internal watchlists. Check for shell company indicators and high-risk jurisdiction associations. "
            "Return match confidence levels and source references."
        ),
        "risk_assessment": (
            "You are a Risk Assessment agent for financial compliance. "
            "Consolidate findings from identity verification and AML screening to produce a composite risk score (0-100). "
            "Consider factors: jurisdiction risk, PEP status, adverse media hits, document discrepancies, transaction pattern anomalies. "
            "Classify risk as low_risk (0-30), medium_risk (31-70), or high_risk (71-100) with detailed rationale."
        ),
        "report_generation": (
            "You are a Regulatory Report Generation agent. "
            "Generate a comprehensive compliance report including: customer identification summary, screening results, "
            "risk assessment findings, and recommended actions. Format output for SOC 2 and PCI-DSS audit trail requirements. "
            "Include timestamped evidence references for each compliance check performed."
        ),
    }
    return prompts.get(name, f"You are {name}. Process the compliance input and produce a refined output.")
