from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BAD_TARGET_MARKERS = ("id", "date", "time", "name", "url", "path", "source_file", "index")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def dataset_urls(dataset_report: dict, limit: int = 3) -> list[str]:
    urls = []
    for candidate in dataset_report.get("dataset_candidates", []):
        for item in candidate.get("direct_files", []):
            url = str(item.get("url", "")).strip()
            if url:
                urls.append(url)
            if len(urls) >= limit:
                return list(dict.fromkeys(urls))
    return list(dict.fromkeys(urls))


def dataset_name_for_url(dataset_report: dict, selected_url: str) -> str:
    for candidate in dataset_report.get("dataset_candidates", []):
        for item in candidate.get("direct_files", []):
            if item.get("url") == selected_url:
                return str(candidate.get("name") or "dataset_agent_candidates")
    for candidate in dataset_report.get("dataset_candidates", []):
        name = str(candidate.get("name", "")).strip()
        if name:
            return name
    return "dataset_agent_candidates"


def file_matches_url(schema_file: str, url: str) -> bool:
    file_name = Path(schema_file).name.lower()
    url_name = Path(url.split("?", 1)[0]).name.lower()
    return bool(file_name and url_name and file_name.endswith(url_name))


def schema_for_url(schema_report: dict, selected_url: str) -> dict:
    schemas = schema_report.get("schemas", [])
    for schema in schemas:
        if file_matches_url(str(schema.get("file", "")), selected_url):
            return schema
    return schemas[0] if schemas else {}


def score_target(column: str, target_candidates: list[str], research_question: str) -> int:
    normalized = normalize_name(column)
    context = normalize_name(research_question)
    score = 0
    if column in target_candidates:
        score += 100
    for candidate in target_candidates:
        candidate_norm = normalize_name(candidate)
        if normalized == candidate_norm:
            score += 80
        elif candidate_norm and candidate_norm in normalized:
            score += 45
    for token in context.split("_"):
        if token and len(token) > 2 and token in normalized:
            score += 15
    if any(marker in normalized for marker in BAD_TARGET_MARKERS):
        score -= 80
    return score


def choose_target(schema: dict, research_question: str) -> tuple[str, str, str]:
    columns = [str(column) for column in schema.get("columns", [])]
    target_candidates = [str(column) for column in schema.get("target_candidates", [])]
    if not columns:
        return "TO_VERIFY", "TO_VERIFY", "No columns were available for target selection."

    scored = [
        (score_target(column, target_candidates, research_question), column)
        for column in columns
    ]
    scored.sort(key=lambda item: (-item[0], columns.index(item[1])))
    best_score, best_column = scored[0]
    if best_score <= 0:
        return "AUTO_TARGET", "low", "No credible target candidate was found; Experiment Agent should infer target after loading."
    confidence = "high" if best_score >= 100 else "medium"
    return best_column, confidence, f"Selected `{best_column}` because it best matches target hints and the research question."


def infer_task_type(target_column: str, schema: dict) -> str:
    if target_column in {"AUTO_TARGET", "TO_VERIFY"}:
        return "auto"

    profile = (schema.get("column_profiles") or {}).get(target_column, {})
    rows = int(schema.get("rows") or 0)
    non_empty = int(profile.get("non_empty") or 0)
    unique_count = int(profile.get("unique_count") or 0)
    numeric_fraction = float(profile.get("numeric_fraction") or 0.0)

    if not profile or non_empty == 0:
        return "auto"
    if numeric_fraction >= 0.9 and unique_count > max(20, min(100, rows * 0.05)):
        return "regression"
    return "classification"


def run_target_agent(research_question: str, dataset_report: dict, schema_report: dict) -> dict:
    print("[Target Agent] Selecting dataset and target column...")
    urls = dataset_urls(dataset_report)
    if not urls:
        return {
            "selected_dataset_name": "TO_VERIFY",
            "selected_file_url": "TO_VERIFY",
            "target_column": "TO_VERIFY",
            "task_type": "TO_VERIFY",
            "feature_columns": ["TO_VERIFY"],
            "confidence": "none",
            "reason": "No direct dataset URLs were available.",
            "limitations": ["Proposal needs a readable public dataset before execution."],
        }

    selected_url = urls[0]
    schema = schema_for_url(schema_report, selected_url)
    target_column, confidence, reason = choose_target(schema, research_question)
    return {
        "selected_dataset_name": dataset_name_for_url(dataset_report, selected_url),
        "selected_file_url": selected_url,
        "target_column": target_column,
        "task_type": infer_task_type(target_column, schema),
        "feature_columns": ["AUTO_NUMERIC"],
        "confidence": confidence,
        "reason": reason,
        "rows": schema.get("rows", 0),
        "columns_sample": schema.get("columns", [])[:25],
        "target_candidates": schema.get("target_candidates", [])[:8],
        "target_profile": (schema.get("column_profiles") or {}).get(target_column, {}),
        "limitations": [
            "Target selection is based on schema names and inspected value profiles; Experiment Agent should confirm during execution."
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select executable target column from schema evidence.")
    parser.add_argument("research_question")
    parser.add_argument("--dataset-report", required=True)
    parser.add_argument("--schema-report", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    dataset_report = json.loads(Path(args.dataset_report).read_text(encoding="utf-8"))
    schema_report = json.loads(Path(args.schema_report).read_text(encoding="utf-8"))
    print(json.dumps(run_target_agent(args.research_question, dataset_report, schema_report), indent=2))
