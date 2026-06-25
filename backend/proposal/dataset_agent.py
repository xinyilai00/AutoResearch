from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .. import proposal_agent
except ImportError:
    import proposal_agent


def build_dataset_report(sources: list[dict]) -> dict:
    candidates = []
    for source in sources:
        files = source.get("data_files") or source.get("csv_files") or []
        direct_files = []
        for item in files:
            url = item.get("raw_url", "")
            if url and proposal_agent.looks_like_data_file_path(url):
                direct_files.append({"url": url, "path": item.get("path", "")})
        if not direct_files:
            continue
        candidates.append(
            {
                "name": source.get("name", "Unnamed dataset"),
                "source": source.get("source", "Public source"),
                "page_url": source.get("url", ""),
                "description": source.get("description", ""),
                "direct_files": direct_files,
            }
        )
    return {"candidate_count": len(candidates), "dataset_candidates": candidates}


def dataset_report_to_prompt_text(report: dict) -> str:
    candidates = report.get("dataset_candidates", [])
    if not candidates:
        return "No readable direct public dataset files were found automatically."

    lines = ["DATASET CANDIDATES:"]
    for index, candidate in enumerate(candidates, 1):
        lines.append(f"{index}. {candidate.get('name')} ({candidate.get('source')})")
        lines.append(f"   Page: {candidate.get('page_url')}")
        lines.append(f"   Description: {candidate.get('description') or 'N/A'}")
        lines.append("   Direct files:")
        for item in candidate.get("direct_files", [])[:12]:
            lines.append(f"   - {item.get('url')} (path: {item.get('path')})")
    return "\n".join(lines)


def run_dataset_agent(research_question: str, output_dir: str | Path | None = None, limit: int = 5) -> dict:
    print("[Dataset Agent] Searching readable public dataset files...")
    sources = proposal_agent.search_public_datasets(research_question, limit=limit)
    report = build_dataset_report(sources)

    if output_dir is not None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "dataset_candidates.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output_path / "dataset_candidates.md").write_text(dataset_report_to_prompt_text(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find readable public dataset files.")
    parser.add_argument("research_question")
    parser.add_argument("--out", default="paper_runs/latest/proposal/dataset")
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(dataset_report_to_prompt_text(run_dataset_agent(args.research_question, args.out, args.limit)))
