from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ..agent_api import call_agent_api
    from ..config import ANALYSIS_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import ANALYSIS_PRINCIPAL_ID


ANALYSIS_PROMPT = """
You are the Analysis Agent in an autonomous research pipeline.

Input:
- Hypothesis Agent output
- Dataset Agent output
- Schema Agent output

Job:
Create the final executable EXPERIMENT EXECUTION SPEC for the Experiment Agent.

Rules:
- Only use direct dataset URLs listed by the Dataset Agent.
- Prefer columns inspected by the Schema Agent.
- If a target candidate exists, choose the best target column.
- If rows loaded but no target candidate exists, use AUTO_TARGET.
- If no readable files loaded or the data cannot answer the hypothesis, use NEEDS_NEW_RUNNER.
- Do not invent URLs, columns, metrics, datasets, or results.
- Output one valid JSON object only.

Required JSON keys:
runner_type, task_type, dataset_url, dataset_urls, dataset_name, target_column,
feature_columns, baseline, success_metric, success_threshold, threshold_direction,
notes_for_experiment_agent.
"""


def extract_json_object(text: str) -> dict | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])
    return None


def dataset_urls(dataset_report: dict, limit: int = 5) -> list[str]:
    urls = []
    for candidate in dataset_report.get("dataset_candidates", []):
        for item in candidate.get("direct_files", []):
            url = item.get("url", "")
            if url:
                urls.append(url)
            if len(urls) >= limit:
                return list(dict.fromkeys(urls))
    return list(dict.fromkeys(urls))


def first_target_candidate(schema_report: dict) -> str:
    for schema in schema_report.get("schemas", []):
        candidates = schema.get("target_candidates") or []
        if candidates:
            return str(candidates[0])
    return "AUTO_TARGET" if schema_report.get("rows_loaded", 0) else "TO_VERIFY"


def success_defaults(task_type: str, can_attempt_baseline: bool) -> tuple[str, float, str]:
    if not can_attempt_baseline:
        return "inspect", 1.0, "greater_or_equal"
    if task_type == "regression":
        return "r2", 0.05, "greater_or_equal"
    return "accuracy", 0.55, "greater_or_equal"


def compact_text(text: str, limit: int = 1500) -> str:
    cleaned = " ".join(str(text).split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def compact_evidence_packet(
    hypothesis_output: str,
    dataset_report: dict,
    schema_report: dict,
    target_packet: dict | None = None,
) -> dict:
    urls = dataset_urls(dataset_report, limit=3)
    selected_dataset = {}
    for candidate in dataset_report.get("dataset_candidates", []):
        direct_files = candidate.get("direct_files", [])
        if direct_files:
            selected_dataset = {
                "name": candidate.get("name", "dataset_agent_candidates"),
                "source": candidate.get("source", ""),
                "description": compact_text(candidate.get("description", ""), 180),
                "direct_files": direct_files[:3],
            }
            break

    schemas = []
    for schema in schema_report.get("schemas", [])[:3]:
        schemas.append(
            {
                "file": schema.get("file"),
                "rows": schema.get("rows"),
                "type": schema.get("type"),
                "target_candidates": schema.get("target_candidates", [])[:5],
                "columns": schema.get("columns", [])[:25],
                "target_profiles": {
                    column: (schema.get("column_profiles") or {}).get(column, {})
                    for column in schema.get("target_candidates", [])[:3]
                },
            }
        )

    return {
        "hypothesis": compact_text(hypothesis_output, 1200),
        "dataset": selected_dataset,
        "dataset_urls": urls,
        "files_loaded": schema_report.get("files_loaded", 0),
        "rows_loaded": schema_report.get("rows_loaded", 0),
        "schemas": schemas,
        "selected_target": target_packet or {},
        "preferred_target": (target_packet or {}).get("target_column") or first_target_candidate(schema_report),
    }


def fallback_analysis_spec(
    dataset_report: dict,
    schema_report: dict,
    reason: str,
    target_packet: dict | None = None,
) -> dict:
    urls = dataset_urls(dataset_report)
    if not urls:
        return {
            "runner_type": "NEEDS_NEW_RUNNER",
            "task_type": "TO_VERIFY",
            "dataset_url": "TO_VERIFY",
            "dataset_urls": ["TO_VERIFY"],
            "dataset_name": "TO_VERIFY",
            "target_column": "TO_VERIFY",
            "feature_columns": ["TO_VERIFY"],
            "baseline": "TO_VERIFY",
            "success_metric": "TO_VERIFY",
            "success_threshold": 1.0,
            "threshold_direction": "TO_VERIFY",
            "notes_for_experiment_agent": f"No executable dataset files were found. Reason: {reason}",
        }

    all_csv = all(url.lower().split("?", 1)[0].endswith(".csv") for url in urls)
    target_column = str((target_packet or {}).get("target_column") or first_target_candidate(schema_report))
    task_type = str((target_packet or {}).get("task_type") or "")
    has_loaded_rows = bool(schema_report.get("rows_loaded", 0))
    can_attempt_baseline = all_csv or has_loaded_rows
    if can_attempt_baseline and target_column == "TO_VERIFY":
        target_column = "AUTO_TARGET"
    resolved_task_type = task_type if task_type and task_type != "TO_VERIFY" else ("auto" if can_attempt_baseline else "inspect")
    success_metric, success_threshold, threshold_direction = success_defaults(resolved_task_type, can_attempt_baseline)
    return {
        "runner_type": "universal_tabular_csv" if all_csv else "universal_data_file",
        "task_type": resolved_task_type,
        "dataset_url": str((target_packet or {}).get("selected_file_url") or urls[0]),
        "dataset_urls": [str((target_packet or {}).get("selected_file_url"))] if (target_packet or {}).get("selected_file_url") and (target_packet or {}).get("selected_file_url") != "TO_VERIFY" else urls,
        "dataset_name": str((target_packet or {}).get("selected_dataset_name") or "dataset_agent_candidates"),
        "target_column": target_column if can_attempt_baseline else "TO_VERIFY",
        "feature_columns": (target_packet or {}).get("feature_columns") or ["AUTO_NUMERIC"],
        "baseline": "majority_class for classification or mean_prediction for regression",
        "success_metric": success_metric,
        "success_threshold": success_threshold,
        "threshold_direction": threshold_direction,
        "notes_for_experiment_agent": f"Generated by Analysis Agent fallback. Reason: {reason}",
    }


def run_analysis_agent(
    hypothesis_output: str,
    dataset_report: dict,
    schema_report: dict,
    target_packet: dict | None = None,
) -> dict:
    evidence_packet = compact_evidence_packet(hypothesis_output, dataset_report, schema_report, target_packet)
    prompt = f"""{ANALYSIS_PROMPT}

Compact evidence packet:
{json.dumps(evidence_packet, indent=2)}
"""
    try:
        raw = call_agent_api(prompt, "Analysis", ANALYSIS_PRINCIPAL_ID)
        parsed = extract_json_object(raw)
        if isinstance(parsed, dict):
            return parsed
        return fallback_analysis_spec(dataset_report, schema_report, "Analysis Agent did not return valid JSON.", target_packet)
    except Exception as exc:
        print(f"Analysis failed; using fallback. Reason: {exc}")
        return fallback_analysis_spec(dataset_report, schema_report, str(exc), target_packet)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create experiment execution spec from proposal subagent outputs.")
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--dataset-report", required=True)
    parser.add_argument("--schema-report", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    hypothesis = Path(args.hypothesis).read_text(encoding="utf-8")
    dataset_report = json.loads(Path(args.dataset_report).read_text(encoding="utf-8"))
    schema_report = json.loads(Path(args.schema_report).read_text(encoding="utf-8"))
    print(json.dumps(run_analysis_agent(hypothesis, dataset_report, schema_report), indent=2))
