from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ..agent_api import call_agent_api
    from ..config import HYPOTHESIS_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import HYPOTHESIS_PRINCIPAL_ID


HYPOTHESIS_PROMPT = """
You are the Hypothesis Agent in an autonomous research pipeline.

Input:
- selected research question
- deep literature review
- dataset candidates and schema inspection results, when available

Job:
Create only the hypothesis-level proposal plan. Do not search datasets and do not create an execution spec.
The hypothesis must be testable using the provided dataset/schema context.

Rules:
- Treat "experiment" as a public-data analysis experiment.
- Do not propose lab experiments, surveys, physical sensor deployments, or new private data collection.
- Prefer a hypothesis that uses real dataset columns or target candidates from the schema context.
- If a schema target candidate exists, choose one and name it as the dependent variable.
- If no target candidate exists but rows loaded, use AUTO_TARGET and explain that the Experiment Agent should infer the target after loading.
- If no readable schema exists, clearly mark the hypothesis as provisional.
- State what data characteristics are required for the analysis to be executable.
- Do not fabricate citations, datasets, statistics, or results.
- Use author-year citations only if they are present in the input.

Output exactly:
RESEARCH QUESTION:
[question]

HYPOTHESIS:
[testable hypothesis]

ANALYSIS GOAL:
[what the analysis must determine]

REQUIRED DATA CHARACTERISTICS:
- [required columns/labels/populations/time range/etc.]

KEY VARIABLES:
- Independent variables: [...]
- Dependent variables: [...]
- Control variables: [...]

SUCCESS CRITERIA:
- [metric/comparison that would support the hypothesis]
"""


def read_text_or_path(value: str | Path) -> str:
    path = Path(value)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return str(value)


def first_dataset_name(dataset_report: dict | None) -> str:
    for candidate in (dataset_report or {}).get("dataset_candidates", []):
        name = str(candidate.get("name", "")).strip()
        if name:
            return name
    return "the selected public dataset"


def first_target_candidate(schema_report: dict | None, target_packet: dict | None = None) -> str:
    selected = str((target_packet or {}).get("target_column", "")).strip()
    if selected:
        return selected
    for schema in (schema_report or {}).get("schemas", []):
        candidates = schema.get("target_candidates") or []
        if candidates:
            return str(candidates[0])
    return "AUTO_TARGET" if (schema_report or {}).get("rows_loaded", 0) else "TO_VERIFY"


def first_feature_candidates(schema_report: dict | None, target_column: str) -> list[str]:
    for schema in (schema_report or {}).get("schemas", []):
        columns = [str(column) for column in schema.get("columns", [])]
        features = [
            column
            for column in columns
            if column != target_column and column.lower() not in {"source_file", "id", "index"}
        ]
        if features:
            return features[:8]
    return ["AUTO_NUMERIC"]


def compact_text(text: str, limit: int = 1500) -> str:
    cleaned = " ".join(str(text).split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def fallback_hypothesis(
    research_question: str,
    reason: str,
    dataset_report: dict | None = None,
    schema_report: dict | None = None,
    target_packet: dict | None = None,
) -> str:
    dataset_name = first_dataset_name(dataset_report)
    target_column = first_target_candidate(schema_report, target_packet)
    feature_candidates = first_feature_candidates(schema_report, target_column)
    target_phrase = (
        "an inferred outcome column selected by the Experiment Agent"
        if target_column == "AUTO_TARGET"
        else f"the `{target_column}` outcome column"
    )
    return f"""RESEARCH QUESTION:
{research_question}

HYPOTHESIS:
In {dataset_name}, available predictor columns can predict {target_phrase} better than a simple majority-class or mean-prediction baseline.

ANALYSIS GOAL:
Evaluate whether the public dataset contains enough predictive signal to answer the research question using a reproducible tabular data analysis.

REQUIRED DATA CHARACTERISTICS:
- Public/downloadable dataset files.
- Target column: {target_column}
- Candidate feature columns: {", ".join(feature_candidates)}

KEY VARIABLES:
- Independent variables: {", ".join(feature_candidates)}
- Dependent variables: {target_column}
- Control variables: source file, dataset coverage, missingness, and train/test split.

SUCCESS CRITERIA:
- The analysis uses reproducible public data.
- The evaluated model or baseline produces a measurable metric for {target_column}.

Fallback reason: {reason}
"""


def schema_context_text(dataset_report: dict | None, schema_report: dict | None, target_packet: dict | None = None) -> str:
    if not dataset_report and not schema_report:
        return "No dataset/schema context was provided."
    compact_datasets = []
    for candidate in (dataset_report or {}).get("dataset_candidates", [])[:3]:
        compact_datasets.append(
            {
                "name": candidate.get("name"),
                "source": candidate.get("source"),
                "description": compact_text(str(candidate.get("description", "")), 180),
                "direct_files": candidate.get("direct_files", [])[:3],
            }
        )
    compact_schemas = []
    for schema in (schema_report or {}).get("schemas", [])[:3]:
        compact_schemas.append(
            {
                "file": schema.get("file"),
                "type": schema.get("type"),
                "rows": schema.get("rows"),
                "target_candidates": schema.get("target_candidates", [])[:5],
                "columns": schema.get("columns", [])[:20],
                "target_profiles": {
                    column: (schema.get("column_profiles") or {}).get(column, {})
                    for column in schema.get("target_candidates", [])[:3]
                },
            }
        )
    compact = {
        "datasets": compact_datasets,
        "files_loaded": (schema_report or {}).get("files_loaded", 0),
        "rows_loaded": (schema_report or {}).get("rows_loaded", 0),
        "schemas": compact_schemas,
        "selected_target": target_packet or {},
    }
    return json.dumps(compact, indent=2)


def run_hypothesis_agent(
    research_question: str,
    deep_literature_review: str,
    dataset_report: dict | None = None,
    schema_report: dict | None = None,
    target_packet: dict | None = None,
) -> str:
    prompt = f"""{HYPOTHESIS_PROMPT}

Selected research question:
{research_question}

Deep literature review:
{compact_text(deep_literature_review, 1200)}

Dataset, schema, and selected target context:
{schema_context_text(dataset_report, schema_report, target_packet)}
"""
    try:
        return call_agent_api(prompt, "Hypothesis", HYPOTHESIS_PRINCIPAL_ID)
    except Exception as exc:
        print(f"Hypothesis failed; using fallback. Reason: {exc}")
        return fallback_hypothesis(research_question, str(exc), dataset_report, schema_report, target_packet)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate hypothesis-level proposal plan.")
    parser.add_argument("research_question")
    parser.add_argument("--deep-literature", default="")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(run_hypothesis_agent(args.research_question, read_text_or_path(args.deep_literature)))
