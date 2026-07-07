from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

_lock = Lock()

compliance_call_counts: dict[str, int] = defaultdict(int)
compliance_latency_samples: dict[str, list[float]] = defaultdict(list)
compliance_token_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"prompt": 0, "completion": 0})
verification_start_times: dict[str, float] = {}
false_positive_count: int = 0
false_negative_count: int = 0


def record_compliance_call(workflow_name: str, duration_ms: float, tokens: dict[str, int] | None = None) -> None:
    with _lock:
        compliance_call_counts[workflow_name] += 1
        compliance_latency_samples[workflow_name].append(duration_ms)
        if tokens:
            compliance_token_totals[workflow_name]["prompt"] += tokens.get("prompt", 0)
            compliance_token_totals[workflow_name]["completion"] += tokens.get("completion", 0)


def record_verification_start(case_id: str) -> None:
    with _lock:
        verification_start_times[case_id] = time.perf_counter()


def record_false_positive() -> None:
    global false_positive_count
    with _lock:
        false_positive_count += 1


def record_false_negative() -> None:
    global false_negative_count
    with _lock:
        false_negative_count += 1


def get_compliance_metrics() -> dict[str, Any]:
    with _lock:
        total_calls = sum(compliance_call_counts.values())
        all_latencies = []
        for samples in compliance_latency_samples.values():
            all_latencies.extend(samples)

        now = time.perf_counter()
        active_verifications = sum(1 for t in verification_start_times.values() if now - t < 300)

        metrics: dict[str, Any] = {
            "verifications_per_minute": _compute_rate(compliance_call_counts.get("sequential", 0), 60),
            "false_positive_rate": round(false_positive_count / max(total_calls, 1) * 100, 2),
            "false_negative_rate": round(false_negative_count / max(total_calls, 1) * 100, 2),
            "avg_screening_time_ms": round(sum(all_latencies) / max(len(all_latencies), 1), 2),
            "active_verifications": active_verifications,
            "compliance_call_counts": dict(compliance_call_counts),
            "compliance_latency_stats": {},
            "compliance_token_usage": {
                name: {
                    "prompt": data["prompt"],
                    "completion": data["completion"],
                    "total": data["prompt"] + data["completion"],
                }
                for name, data in compliance_token_totals.items()
            },
        }

        for name, samples in compliance_latency_samples.items():
            if samples:
                metrics["compliance_latency_stats"][name] = {
                    "count": len(samples),
                    "min_ms": round(min(samples), 2),
                    "max_ms": round(max(samples), 2),
                    "avg_ms": round(sum(samples) / len(samples), 2),
                    "p95_ms": round(sorted(samples)[int(len(samples) * 0.95)], 2) if len(samples) >= 20 else None,
                }

    return metrics


def _compute_rate(count: int, window_seconds: float) -> float:
    if count == 0:
        return 0.0
    return round(count / window_seconds, 2)


def print_compliance_metrics() -> None:
    metrics = get_compliance_metrics()
    print("\n=== Fintech Compliance Metrics ===")
    print(f"Verifications/min: {metrics['verifications_per_minute']}")
    print(f"False positive rate: {metrics['false_positive_rate']}%")
    print(f"False negative rate: {metrics['false_negative_rate']}%")
    print(f"Avg screening time: {metrics['avg_screening_time_ms']}ms")
    print(f"Active verifications: {metrics['active_verifications']}")
    print(f"Call counts: {metrics['compliance_call_counts']}")
    print(f"Token usage: {metrics['compliance_token_usage']}")
    print(f"Latency stats: {metrics['compliance_latency_stats']}")
    print("==================================\n")


def reset_compliance_metrics() -> None:
    global false_positive_count, false_negative_count
    with _lock:
        compliance_call_counts.clear()
        compliance_latency_samples.clear()
        compliance_token_totals.clear()
        verification_start_times.clear()
        false_positive_count = 0
        false_negative_count = 0
