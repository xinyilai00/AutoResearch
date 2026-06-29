from __future__ import annotations

import json
import urllib.request
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
    from backend.repo_library import format_repo_metadata, get_repo_by_id, select_repo_for_prompt
except ImportError:
    from pipeline_state import get_experiment_anchor
    from repo_library import format_repo_metadata, get_repo_by_id, select_repo_for_prompt


RAW_GITHUB_BASE = "https://raw.githubusercontent.com"


def fetch_url(url: str) -> str:
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AutoResearch-Proposal"}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"[Proposal Agent] Failed to fetch {url}: {e}")
        return ""


def github_raw_url(repo_name: str, branch: str, file_path: str) -> str:
    return f"{RAW_GITHUB_BASE}/{repo_name}/{branch}/{file_path}"


def fetch_repo_file(repo_name: str, file_path: str) -> tuple[str, str]:
    for branch in ("main", "master"):
        url = github_raw_url(repo_name, branch, file_path)
        content = fetch_url(url)
        if content.strip():
            return file_path, content
    return file_path, ""


def fetch_first_repo_file(repo_name: str, file_paths: list[str]) -> tuple[str, str]:
    for file_path in file_paths:
        label, content = fetch_repo_file(repo_name, file_path)
        if content.strip():
            return label, content
    return "", ""


def read_text_or_path(value: str | Path) -> str:
    if isinstance(value, str) and len(value) > 500:
        return value
    path = Path(value)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return str(value)


def sentence_summary(text: str, max_sentences: int = 2) -> str:
    cleaned = " ".join(str(text).split())
    if not cleaned:
        return "No deep literature context was provided."
    sentences = []
    start = 0
    for index, char in enumerate(cleaned):
        if char in ".!?" and (index + 1 == len(cleaned) or cleaned[index + 1].isspace()):
            sentence = cleaned[start : index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
        if len(sentences) >= max_sentences:
            break
    if sentences:
        return " ".join(sentences[:max_sentences])
    return cleaned


def run_proposal_stage(research_question: str, deep_literature_review: str | Path) -> str:
    print("\n[Proposal Agent] Building proposal from selected repo metadata...")
    anchor = get_experiment_anchor()
    repo_id = anchor.get("repo_id", "")
    repo_url = anchor["repo_url"]
    hypothesis = anchor["hypothesis"]

    deep_lit = sentence_summary(read_text_or_path(deep_literature_review), max_sentences=2)
    selected_repo = get_repo_by_id(repo_id) or select_repo_for_prompt(
        "\n".join([research_question, deep_lit, repo_url, hypothesis])
    )
    datasets = selected_repo.get("datasets", [])
    primary_dataset = datasets[0] if datasets else {}
    dependencies = selected_repo.get("dependencies", [])
    entrypoints = selected_repo.get("entrypoints", [])
    metrics = selected_repo.get("metrics", [])
    tasks = selected_repo.get("tasks", [])

    requirements_label, requirements = fetch_first_repo_file(
        selected_repo["name"],
        selected_repo.get("requirements_files", []),
    )
    source_label, source_excerpt = fetch_first_repo_file(
        selected_repo["name"],
        selected_repo.get("source_files", []),
    )
    if requirements:
        requirements_block = f"Source file: {requirements_label}\n\n{requirements}"
    else:
        requirements_block = "No repo-specific requirement/config file was fetched for this metadata entry."

    if source_excerpt:
        source_block = f"Source file: {source_label}\n\n{source_excerpt[:3000]}"
    else:
        source_block = "No repo-specific source/example excerpt was fetched for this metadata entry."

    proposal = f"""PROPOSAL SUMMARY
Research question: {research_question}
Repo: {repo_url}
Hypothesis: {hypothesis}

LOCAL REPO LIBRARY MATCH:
{format_repo_metadata(selected_repo)}

EXPERIMENT OVERVIEW:
This proposal outlines a benchmark-oriented replication study using {selected_repo['name']}.
The goal is to run or adapt the repository's documented workflow for the selected prompt,
use its public dataset resources, and evaluate the result with the repository's benchmark metrics.

REPOSITORY:
- URL: {repo_url}
- Expected entrypoints: {', '.join(entrypoints) if entrypoints else 'Inspect repository examples and scripts'}
- Dependencies: {', '.join(dependencies) if dependencies else 'Inspect repository requirements'}

BENCHMARK TASKS:
{json.dumps(tasks, indent=2)}

DATASET:
{json.dumps(primary_dataset, indent=2)}

METRICS:
{json.dumps(metrics, indent=2)}

REPLICATION STEPS:
1. Clone the repository:
   git clone {repo_url}
2. Create or reuse an isolated virtual environment.
3. Install only the dependencies required by the selected benchmark.
4. Run the documented entrypoint or example script.
5. Capture benchmark metrics, runtime, and any failure logs.

SUCCESS CRITERIA:
- The benchmark runs without errors on the selected public dataset.
- The output includes at least one primary metric: {metrics[0] if metrics else 'benchmark performance'}.
- Results are logged and captured for the paper.

EXPECTED OUTPUT:
- Selected repo and dataset provenance
- Benchmark metric values
- Runtime and reproducibility notes

REQUIREMENTS FILE CONTENTS:
{requirements_block}

SOURCE OR EXAMPLE EXCERPT (first 3000 chars):
{source_block}

DEEP LITERATURE CONTEXT:
{deep_lit}
"""

    print("[Proposal Agent] Proposal generated successfully.")
    return proposal


if __name__ == "__main__":
    question = input("Enter research question: ")
    review = input("Enter deep literature review path or text: ")
    print(run_proposal_stage(question, review))
