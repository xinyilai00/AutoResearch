from __future__ import annotations

import os

try:
    from ..config import PRINCIPAL_ID
    from ..experiment_agent import SUPPORTED_METRICS, SUPPORTED_RUNNER_TYPES, SUPPORTED_TASK_TYPES
except ImportError:
    from config import PRINCIPAL_ID
    from experiment_agent import SUPPORTED_METRICS, SUPPORTED_RUNNER_TYPES, SUPPORTED_TASK_TYPES


EXPERIMENT_PRINCIPAL_ID = os.getenv("EXPERIMENT_PRINCIPAL_ID", PRINCIPAL_ID)


def run_method_agent(spec: dict, proposal: str = "") -> dict:
    runner_type = str(spec.get("runner_type", "")).lower()
    task_type = str(spec.get("task_type", "")).lower()
    metric = str(spec.get("success_metric", "")).lower()
    baseline = str(spec.get("baseline", "")).strip()

    issues = []
    if runner_type not in SUPPORTED_RUNNER_TYPES:
        issues.append(f"Unsupported runner_type: {runner_type or 'missing'}")
    if task_type not in SUPPORTED_TASK_TYPES:
        issues.append(f"Unsupported task_type: {task_type or 'missing'}")
    if metric not in SUPPORTED_METRICS:
        issues.append(f"Unsupported success_metric: {metric or 'missing'}")
    if not baseline or baseline.upper() == "TO_VERIFY":
        issues.append("Baseline is missing or TO_VERIFY.")

    return {
        "agent": "method",
        "principal_id": EXPERIMENT_PRINCIPAL_ID,
        "runner_type": runner_type,
        "task_type": task_type,
        "success_metric": metric,
        "baseline": baseline or "TO_VERIFY",
        "issues": issues,
        "ready": not issues,
    }
