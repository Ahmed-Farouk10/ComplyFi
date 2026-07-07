from __future__ import annotations

import json
import time
from collections.abc import Callable, Awaitable
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from src.evaluation.judges import judge_response

DATASET_DIR = Path(__file__).resolve().parent / "datasets"
RESULTS_FILE = Path(__file__).resolve().parent.parent.parent / "compliance-eval-results.json"


def load_dataset(filename: str = "sample.json") -> list[dict[str, Any]]:
    filepath = DATASET_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


async def run_evaluation(
    client: AsyncOpenAI,
    model: str,
    agent_fn: Callable[[str], Awaitable[str]],
    dataset_filename: str = "sample.json",
) -> dict[str, Any]:
    test_cases = load_dataset(dataset_filename)
    if not test_cases:
        return {"error": "No compliance test cases found", "results": [], "summary": {}}

    results: list[dict[str, Any]] = []
    total_scores = {
        "compliance_accuracy": 0.0,
        "false_positive_rate": 0.0,
        "false_negative_rate": 0.0,
        "regulatory_alignment": 0.0,
        "audit_trail_quality": 0.0,
        "overall": 0.0,
    }
    passed = 0
    failed = 0
    false_positives = 0
    false_negatives = 0

    for case in test_cases:
        case_id = case.get("id", "unknown")
        question = case.get("question", "")
        expected_keywords = case.get("expected_keywords", [])
        expected_disposition = case.get("expected_disposition", "PASS")
        min_score = case.get("min_score", 3.0)

        start = time.perf_counter()
        try:
            agent_answer = await agent_fn(question)
        except Exception as exc:
            agent_answer = f"ERROR: {exc}"

        latency_ms = round((time.perf_counter() - start) * 1000)

        eval_result = await judge_response(client, model, question, agent_answer, expected_keywords, expected_disposition)

        case_passed = eval_result["overall"] >= min_score
        if case_passed:
            passed += 1
        else:
            failed += 1

        if eval_result.get("false_positive", False):
            false_positives += 1
        if eval_result.get("false_negative", False):
            false_negatives += 1

        result_entry = {
            "id": case_id,
            "question": question,
            "expected_keywords": expected_keywords,
            "expected_disposition": expected_disposition,
            "min_score": min_score,
            "agent_response": agent_answer,
            "scores": eval_result,
            "passed": case_passed,
            "latency_ms": latency_ms,
        }
        results.append(result_entry)

        for key in total_scores:
            total_scores[key] += eval_result.get(key, 0.0)

    n = len(results) or 1
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / n * 100, 1),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "false_positive_rate": round(false_positives / n * 100, 1),
        "false_negative_rate": round(false_negatives / n * 100, 1),
        "avg_scores": {k: round(v / n, 2) for k, v in total_scores.items()},
    }

    output = {"results": results, "summary": summary}

    try:
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    except OSError:
        pass

    return output
