from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from .. import experiment_agent
except ImportError:
    import experiment_agent


GENERIC_TARGET_HINTS = (
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

CONTEXT_STOPWORDS = {
    "about",
    "across",
    "after",
    "analysis",
    "and",
    "based",
    "between",
    "can",
    "data",
    "dataset",
    "datasets",
    "does",
    "effect",
    "from",
    "how",
    "into",
    "model",
    "models",
    "predict",
    "prediction",
    "public",
    "research",
    "the",
    "this",
    "through",
    "using",
    "what",
    "when",
    "with",
}

DOMAIN_TARGET_HINTS = {
    "injury": ["injury", "injured", "injury_status", "injury_label", "is_injured"],
    "injuries": ["injury", "injured", "injury_status", "injury_label", "is_injured"],
    "sport": ["winner", "result", "outcome", "home_win", "away_win", "ftr", "score"],
    "sports": ["winner", "result", "outcome", "home_win", "away_win", "ftr", "score"],
    "match": ["winner", "result", "outcome", "home_win", "away_win", "ftr", "score"],
    "game": ["winner", "result", "outcome", "home_win", "away_win", "score"],
    "win": ["winner", "win", "home_win", "away_win", "result", "outcome"],
    "winner": ["winner", "win", "result", "outcome"],
    "return": ["return", "returns", "excess_return", "next_return", "target_return"],
    "returns": ["return", "returns", "excess_return", "next_return", "target_return"],
    "price": ["price", "close", "adj_close", "target_price", "next_price"],
    "sentiment": ["sentiment", "label", "polarity", "class"],
    "classification": ["label", "class", "category", "target", "outcome"],
    "diagnosis": ["diagnosis", "disease", "condition", "label", "class"],
    "risk": ["risk", "default", "failure", "event", "outcome"],
    "rating": ["rating", "score", "target", "outcome"],
}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def context_tokens(context: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", context.lower())
    return [
        token
        for token in dict.fromkeys(tokens)
        if token not in CONTEXT_STOPWORDS and len(token) <= 32
    ]


def target_hints_for_context(context: str) -> list[str]:
    hints = list(GENERIC_TARGET_HINTS)
    tokens = context_tokens(context)
    for token in tokens:
        hints.append(token)
        hints.extend(DOMAIN_TARGET_HINTS.get(token, []))
    return list(dict.fromkeys(normalize_name(hint) for hint in hints if hint))


def dataset_context(dataset_report: dict) -> str:
    parts = []
    for candidate in dataset_report.get("dataset_candidates", []):
        parts.extend(
            [
                str(candidate.get("name", "")),
                str(candidate.get("source", "")),
                str(candidate.get("description", "")),
                str(candidate.get("page_url", "")),
            ]
        )
        for item in candidate.get("direct_files", []):
            parts.extend([str(item.get("url", "")), str(item.get("path", ""))])
    return "\n".join(parts)


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


def target_candidates(columns: list[str], context: str = "") -> list[str]:
    hints = target_hints_for_context(context)
    scored = []
    for column in columns:
        normalized = normalize_name(column)
        if not normalized or normalized in {"source_file", "id", "index"}:
            continue
        score = 0
        for hint in hints:
            if normalized == hint:
                score += 100
            elif normalized.endswith(f"_{hint}") or normalized.startswith(f"{hint}_"):
                score += 70
            elif hint in normalized:
                score += 40
        if any(generic in normalized for generic in GENERIC_TARGET_HINTS):
            score += 20
        if any(marker in normalized for marker in ("id", "date", "time", "name", "url", "path")):
            score -= 30
        if score > 0:
            scored.append((score, column))
    scored.sort(key=lambda item: (-item[0], columns.index(item[1])))
    return list(dict.fromkeys(column for _, column in scored))


def inspect_dataset_urls(dataset_urls: list[str], output_dir: str | Path, context: str = "") -> dict:
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
                "target_candidates": target_candidates(columns, context),
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


def run_schema_agent(
    dataset_report: dict,
    output_dir: str | Path | None = "paper_runs/latest/proposal/schema",
    research_question: str = "",
) -> dict:
    print("[Schema Agent] Inspecting readable candidate schemas...")
    urls = flatten_dataset_urls(dataset_report)
    output_path = Path(output_dir) if output_dir is not None else Path("/private/tmp/autoresearch-schema")
    context = research_question + "\n" + dataset_context(dataset_report)
    report = inspect_dataset_urls(urls, output_path, context)
    if output_dir is not None:
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
