from __future__ import annotations

import os

try:
    from ..config import PRINCIPAL_ID
except ImportError:
    from config import PRINCIPAL_ID


EXPERIMENT_PRINCIPAL_ID = os.getenv("EXPERIMENT_PRINCIPAL_ID", PRINCIPAL_ID)


def run_risk_agent(spec: dict, proposal: str = "") -> dict:
    runner_type = str(spec.get("runner_type", "")).lower()
    notes = str(spec.get("notes_for_experiment_agent", ""))
    risks = []

    if runner_type == "needs_new_runner":
        risks.append("Proposal requires a specialized runner, so the current safe runners may only inspect data.")
    if "scrap" in notes.lower():
        risks.append("Spec mentions scraping, which is not supported by the safe experiment runner.")
    if "kaggle" in notes.lower():
        risks.append("Spec mentions Kaggle; credentialed Kaggle downloads are not supported unless a direct file is provided.")
    if "deep learning" in notes.lower() or "transformer" in notes.lower() or "lstm" in notes.lower():
        risks.append("Spec mentions advanced modeling; current safe runners only run simple baselines unless a specialized runner exists.")
    if "api" in notes.lower() and "direct" not in notes.lower():
        risks.append("Spec may require API pagination or authentication, which is not supported by universal file runners.")

    return {
        "agent": "risk",
        "principal_id": EXPERIMENT_PRINCIPAL_ID,
        "risks": risks,
        "ready": runner_type != "needs_new_runner",
    }
