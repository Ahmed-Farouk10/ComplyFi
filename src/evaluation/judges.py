from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI


async def judge_response(
    client: AsyncOpenAI,
    model: str,
    question: str,
    response: str,
    expected_keywords: list[str],
    expected_disposition: str = "PASS",
) -> dict[str, Any]:
    rubric = f"""You are a compliance evaluator scoring a fintech compliance AI agent's response on a 1-5 scale for each criterion.

**Compliance Scenario:** {question}
**Expected keywords:** {", ".join(expected_keywords)}
**Expected risk disposition:** {expected_disposition}
**Response to evaluate:** {response}

Score each criterion from 1 (poor) to 5 (excellent):

1. **compliance_accuracy**: Does the response correctly identify compliance issues (PEP, sanctions, high-risk jurisdictions, document discrepancies)? Are regulatory standards (SOC 2, PCI-DSS, GDPR) properly referenced?

2. **false_positive_rate**: If expected disposition is PASS, does the response incorrectly flag the case? Score 5 means no false positives. Score 1 means the response incorrectly flagged a clean case.

3. **false_negative_rate**: If expected disposition is FLAGGED or ESCALATE, does the response fail to identify known issues? Score 5 means all issues were caught (no false negatives). Score 1 means critical issues were missed.

4. **regulatory_alignment**: Does the response reference appropriate regulations? Is the recommended action aligned with SOC 2, PCI-DSS, GDPR, and AML/KYC requirements?

5. **audit_trail_quality**: Does the response include sufficient detail for an audit trail? Are findings timestamped, traceable, and evidence-backed? Would this satisfy a regulatory auditor?

Respond ONLY with a JSON object:
{{"compliance_accuracy": <int>, "false_positive_rate": <int>, "false_negative_rate": <int>, "regulatory_alignment": <int>, "audit_trail_quality": <int>, "explanation": "<brief>", "false_positive": <bool>, "false_negative": <bool>}}"""

    try:
        judge_response_obj = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": rubric}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = judge_response_obj.choices[0].message.content or "{}"
        scores = json.loads(raw)
    except Exception:
        scores = {
            "compliance_accuracy": 1,
            "false_positive_rate": 1,
            "false_negative_rate": 1,
            "regulatory_alignment": 1,
            "audit_trail_quality": 1,
            "explanation": "Compliance judge evaluation failed.",
            "false_positive": False,
            "false_negative": False,
        }

    overall = (
        scores.get("compliance_accuracy", 1)
        + scores.get("false_positive_rate", 1)
        + scores.get("false_negative_rate", 1)
        + scores.get("regulatory_alignment", 1)
        + scores.get("audit_trail_quality", 1)
    ) / 5.0

    return {
        "overall": round(overall, 2),
        "compliance_accuracy": scores.get("compliance_accuracy", 1),
        "false_positive_rate": scores.get("false_positive_rate", 1),
        "false_negative_rate": scores.get("false_negative_rate", 1),
        "regulatory_alignment": scores.get("regulatory_alignment", 1),
        "audit_trail_quality": scores.get("audit_trail_quality", 1),
        "explanation": scores.get("explanation", ""),
        "false_positive": scores.get("false_positive", False),
        "false_negative": scores.get("false_negative", False),
    }
