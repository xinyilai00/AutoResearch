from __future__ import annotations

import os

try:
    from ..config import PRINCIPAL_ID
except ImportError:
    from config import PRINCIPAL_ID


EXPERIMENT_PRINCIPAL_ID = os.getenv("EXPERIMENT_PRINCIPAL_ID", PRINCIPAL_ID)


def run_schema_agent(spec: dict, proposal: str = "") -> dict:
    target_column = str(spec.get("target_column", "")).strip()
    feature_columns = spec.get("feature_columns", [])
    if not isinstance(feature_columns, list):
        feature_columns = [str(feature_columns)]

    issues = []
    if not target_column or target_column.upper() == "TO_VERIFY":
        issues.append("Target column is missing or TO_VERIFY.")

    can_infer_target = target_column.upper() in {"AUTO_TARGET", "TO_VERIFY", ""}
    if not feature_columns or feature_columns == ["TO_VERIFY"]:
        issues.append("Feature columns are missing or TO_VERIFY.")

    return {
        "agent": "schema",
        "principal_id": EXPERIMENT_PRINCIPAL_ID,
        "target_column": target_column or "TO_VERIFY",
        "feature_columns": feature_columns,
        "can_infer_target": can_infer_target,
        "issues": issues,
        "ready": not issues or can_infer_target,
    }
