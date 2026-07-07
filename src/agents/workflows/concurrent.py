from __future__ import annotations

import asyncio
import time
from typing import Any

from openai import AsyncOpenAI


async def run_concurrent(
    client: AsyncOpenAI,
    model: str,
    query: str,
) -> dict[str, Any]:
    subtasks = [
        ("kyc_check", (
            "You are a KYC (Know Your Customer) verification specialist. "
            "Verify customer identity: validate name, date of birth, address, and government-issued ID. "
            "Check against document expiration and format validation rules. "
            "Assess identity verification confidence level (HIGH/MEDIUM/LOW) with specific findings."
        )),
        ("aml_screening", (
            "You are an AML (Anti-Money Laundering) screening specialist. "
            "Screen the entity against OFAC SDN, UN, EU, and UK sanctions lists. "
            "Check PEP databases and adverse media for politically exposed persons. "
            "Flag any watchlist matches with confidence scores and list references."
        )),
        ("fraud_detection", (
            "You are a Fraud Detection specialist for fintech compliance. "
            "Analyze transaction history for suspicious patterns: structuring, rapid movement, high-risk counterparties. "
            "Check for synthetic identity indicators, device fingerprinting anomalies, and velocity checks. "
            "Assign a fraud risk score with supporting evidence."
        )),
        ("sanctions_screening", (
            "You are a Sanctions Screening specialist. "
            "Perform comprehensive sanctions screening across all major lists (OFAC, UN, EU, HMT, DFAT). "
            "Apply fuzzy name matching for aliases and transliterated names. "
            "Check beneficial ownership against sanctioned entities. Return exact match details and disposition."
        )),
    ]

    async def _run_subtask(name: str, system_prompt: str) -> dict[str, Any]:
        step_start = time.perf_counter()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
            )
            output = response.choices[0].message.content or ""
            usage = response.usage
            duration = time.perf_counter() - step_start
            return {
                "agent": name,
                "output": output,
                "tokens": {
                    "prompt": usage.prompt_tokens if usage else 0,
                    "completion": usage.completion_tokens if usage else 0,
                },
                "duration_ms": round(duration * 1000),
                "error": None,
            }
        except Exception as exc:
            return {
                "agent": name,
                "output": None,
                "tokens": {"prompt": 0, "completion": 0},
                "duration_ms": round((time.perf_counter() - step_start) * 1000),
                "error": str(exc),
            }

    results = await asyncio.gather(*(_run_subtask(name, prompt) for name, prompt in subtasks))

    aggregate_prompt = (
        "You are a Compliance Aggregator agent for a fintech compliance platform. "
        "Below are the outputs from parallel screening checks (KYC, AML, Fraud, Sanctions). "
        "Synthesize them into a single unified compliance assessment. "
        "Include: aggregated risk score, flagged issues requiring attention, recommended next actions, "
        "and a clear PASS/FLAGGED/ESCALATE disposition:\n\n"
    )
    for r in results:
        if r["error"] is None:
            aggregate_prompt += f"--- {r['agent']} ---\n{r['output']}\n\n"

    aggregation_start = time.perf_counter()
    try:
        agg_response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": aggregate_prompt}],
            temperature=0.3,
        )
        final_output = agg_response.choices[0].message.content or ""
        agg_usage = agg_response.usage
        agg_duration = time.perf_counter() - aggregation_start
        aggregation = {
            "agent": "compliance_aggregator",
            "output": final_output,
            "tokens": {
                "prompt": agg_usage.prompt_tokens if agg_usage else 0,
                "completion": agg_usage.completion_tokens if agg_usage else 0,
            },
            "duration_ms": round(agg_duration * 1000),
            "error": None,
        }
    except Exception as exc:
        aggregation = {
            "agent": "compliance_aggregator",
            "output": None,
            "tokens": {"prompt": 0, "completion": 0},
            "duration_ms": round((time.perf_counter() - aggregation_start) * 1000),
            "error": str(exc),
        }

    return {"result": aggregation["output"], "trace": results + [aggregation]}
