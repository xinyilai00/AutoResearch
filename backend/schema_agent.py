from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from . import experiment_agent
except ImportError:
    import experiment_agent


TARGET_HINTS = (
    "target",
    "label",
    "class",
    "outcome",
    "result",
    "injury",
    "injured",
    "winner",
    "ftr",
    "y",
)


def flatten_dataset_urls(dataset_report: dict, limit: int = 5) -> list[str]:
    urls = []
    for candidate in dataset_report.get("dataset_candidates", []):
        for item in candidate.get("direct_files", []):
            url = item.get("url", "")
            if url and experiment_agent.looks_like_supported_data_file(url):
                urls.append(url)
            if len(urls) >= limit:
                return list(dict.fromkeys(urls))
    return list(dict.fromkeys(urls))


def target_candidates(columns: list[str]) -> list[str]:
    lowered = {column.lower(): column for column in columns}
    candidates = []
    for hint in TARGET_HINTS:
        for lower, original in lowered.items():
            if hint == lower or hint in lower:
                candidates.append(original)
    return list(dict.fromkeys(candidates))


def inspect_dataset_urls(dataset_urls: list[str], output_dir: str | Path) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    spec = {
        "dataset_urls": dataset_urls,
        "dataset_url": dataset_urls[0] if dataset_urls else "TO_VERIFY",
        "runner_type": "universal_data_file",
        "task_type": "inspect",
        "target_column": "TO_VERIFY",
        "success_metric": "inspect",
    }
    try:
        rows, paths, inventory = experiment_agent.load_universal_data_files(spec, output_path)
    except Exception as exc:
        return {
            "files_loaded": 0,
            "rows_loaded": 0,
            "schemas": [],
            "error": str(exc),
        }

    schemas = []
    for item in inventory:
        columns = item.get("columns", [])
        schemas.append(
            {
                "file": item.get("file"),
                "type": item.get("type"),
                "rows": item.get("rows"),
                "columns": columns,
                "target_candidates": target_candidates(columns),
            }
        )

    return {
        "files_loaded": len(paths),
        "rows_loaded": len(rows),
        "schemas": schemas,
    }


def schema_report_to_prompt_text(report: dict) -> str:
    if report.get("error"):
        return f"SCHEMA INSPECTION ERROR: {report['error']}"
    lines = [
        "SCHEMA AGENT OUTPUT:",
        f"Files loaded: {report.get('files_loaded', 0)}",
        f"Rows loaded: {report.get('rows_loaded', 0)}",
    ]
    for index, schema in enumerate(report.get("schemas", []), 1):
        lines.append(f"{index}. {schema.get('file')}")
        lines.append(f"   Type: {schema.get('type')}")
        lines.append(f"   Rows: {schema.get('rows')}")
        lines.append(f"   Target candidates: {schema.get('target_candidates') or ['AUTO_TARGET']}")
        lines.append(f"   Columns: {', '.join(schema.get('columns', [])[:80])}")
    return "\n".join(lines)


def run_schema_agent(dataset_report: dict, output_dir: str | Path = "paper_runs/latest/proposal/schema") -> dict:
    print("[Schema Agent] Inspecting readable candidate schemas...")
    urls = flatten_dataset_urls(dataset_report)
    report = inspect_dataset_urls(urls, output_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "schema_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_path / "schema_report.md").write_text(schema_report_to_prompt_text(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect dataset candidate schemas.")
    parser.add_argument("--dataset-report", required=True)
    parser.add_argument("--out", default="paper_runs/latest/proposal/schema")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    report = json.loads(Path(args.dataset_report).read_text(encoding="utf-8"))
    print(schema_report_to_prompt_text(run_schema_agent(report, args.out)))
