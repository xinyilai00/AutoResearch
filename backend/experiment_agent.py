from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


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


def extract_execution_spec(proposal: str) -> dict:
    marker = "EXPERIMENT EXECUTION SPEC:"
    index = proposal.upper().find(marker)
    if index == -1:
        raise ValueError("Proposal is missing EXPERIMENT EXECUTION SPEC.")

    text = proposal[index + len(marker):].strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    if start == -1:
        raise ValueError("Execution spec does not contain a JSON object.")

    depth = 0
    in_string = False
    escape = False
    for position in range(start, len(text)):
        char = text[position]
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
                return json.loads(text[start : position + 1])

    raise ValueError("Execution spec JSON object is incomplete.")


def list_existing(paths: list[str]) -> list[str]:
    return [path for path in paths if path and Path(path).exists()]


def question_keywords(text: str) -> set[str]:
    stop = {"can", "does", "the", "and", "over", "with", "from", "using", "dataset", "improve"}
    return {word for word in re.findall(r"[a-z0-9_+-]{3,}", text.lower()) if word not in stop}


def entrypoint_score(entrypoint: str, research_question: str) -> int:
    haystack = entrypoint.lower().replace("_", " ").replace("-", " ")
    keywords = question_keywords(research_question)
    score = sum(25 for keyword in keywords if keyword in haystack)
    if "random forest" in research_question.lower() and "random" in haystack and "forest" in haystack:
        score += 200
    if "logistic regression" in research_question.lower() and "logistic" in haystack:
        score += 160
    if "iris" in research_question.lower() and "iris" in haystack:
        score += 160
    if "template" in haystack or "untitled" in haystack:
        score -= 60
    if "kernel svm" in haystack and "svm" not in keywords:
        score -= 40
    return score


def benchmark_command(repo_path: Path, entrypoints: list[str], research_question: str = "") -> tuple[list[str], Path] | None:
    ranked = sorted(entrypoints, key=lambda item: entrypoint_score(item, research_question), reverse=True)
    for entrypoint in ranked:
        candidate = repo_path / entrypoint
        if not candidate.exists():
            continue
        if candidate.suffix == ".py":
            return [sys.executable, candidate.name], candidate.parent
        if candidate.suffix == ".sh":
            return ["bash", candidate.name], candidate.parent
        if candidate.suffix.lower() == ".r":
            return ["Rscript", candidate.name], candidate.parent
    return None


def generated_replication_script(repo_path: Path, data_files: list[str]) -> Path:
    script_path = repo_path / "autoresearch_replication.py"
    script_path.write_text(
        '''from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path


BAD_TARGET_MARKERS = ("id", "date", "time", "name", "url", "path", "source")
TARGET_HINTS = ("target", "label", "class", "outcome", "result", "winner", "win", "home_win", "ftr", "y")


def read_rows(path: Path) -> list[dict]:
    delimiter = "\\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]


def numeric(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except ValueError:
        return None


def choose_target(rows: list[dict]) -> str:
    columns = list(rows[0].keys())
    scored = []
    for column in columns:
        name = column.lower()
        values = [str(row.get(column, "")).strip() for row in rows[:1000] if str(row.get(column, "")).strip()]
        if not values:
            continue
        unique_count = len(set(values))
        score = 0
        if any(hint == name or hint in name for hint in TARGET_HINTS):
            score += 100
        if 1 < unique_count <= 50:
            score += 25
        if any(marker in name for marker in BAD_TARGET_MARKERS):
            score -= 80
        scored.append((score, column))
    scored.sort(key=lambda item: (-item[0], columns.index(item[1])))
    if not scored or scored[0][0] <= 0:
        raise ValueError("No credible target column found.")
    return scored[0][1]


def infer_task(rows: list[dict], target: str) -> str:
    values = [row.get(target, "") for row in rows[:1000] if str(row.get(target, "")).strip()]
    numeric_values = [numeric(value) for value in values]
    numeric_values = [value for value in numeric_values if value is not None]
    return "regression" if len(numeric_values) == len(values) and len(set(values)) > 20 else "classification"


def baseline(rows: list[dict], target: str, task: str) -> dict:
    split = max(1, int(len(rows) * 0.8))
    train = rows[:split]
    test = rows[split:] or rows[:]
    if task == "classification":
        labels = [row.get(target, "") for row in train if str(row.get(target, "")).strip()]
        prediction = Counter(labels).most_common(1)[0][0]
        correct = sum(1 for row in test if row.get(target, "") == prediction)
        return {"model": "majority_class", "accuracy": correct / len(test), "test_examples": len(test), "prediction": prediction}
    values = [numeric(row.get(target)) for row in train]
    values = [value for value in values if value is not None]
    prediction = sum(values) / len(values)
    actual = [numeric(row.get(target)) for row in test]
    actual = [value for value in actual if value is not None]
    mae = sum(abs(value - prediction) for value in actual) / len(actual)
    return {"model": "mean_prediction", "mae": mae, "test_examples": len(actual), "prediction": prediction}


def main():
    candidate_files = [Path(item) for item in DATA_FILES]
    loaded = []
    for path in candidate_files:
        if path.exists() and path.suffix.lower() in {".csv", ".tsv"}:
            rows = read_rows(path)
            if len(rows) >= 20:
                loaded.append((path, rows))
    if not loaded:
        raise SystemExit("No usable CSV/TSV data file with at least 20 rows was found.")
    path, rows = max(loaded, key=lambda item: len(item[1]))
    target = choose_target(rows)
    task = infer_task(rows, target)
    result = baseline(rows, target, task)
    result.update({"data_file": str(path), "rows": len(rows), "target": target, "task": task})
    Path("autoresearch_replication_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


DATA_FILES = __DATA_FILES__


if __name__ == "__main__":
    main()
'''.replace("__DATA_FILES__", repr(data_files)),
        encoding="utf-8",
    )
    return script_path


def prepare_replication_branch(repo_path: Path) -> dict:
    branch_name = os.getenv("BENCHMARK_REPLICATION_BRANCH", "autoresearch-replication")
    if not (repo_path / ".git").exists():
        return {
            "branch_prepared": False,
            "branch": branch_name,
            "reason": "Repository is not a git checkout.",
        }
    try:
        subprocess.run(
            ["git", "checkout", "-B", branch_name],
            cwd=repo_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        return {
            "branch_prepared": True,
            "branch": branch_name,
            "reason": "Created or reset local replication branch before execution.",
        }
    except Exception as exc:
        return {
            "branch_prepared": False,
            "branch": branch_name,
            "reason": str(exc),
        }


def safe_run_benchmark(
    repo_path: Path,
    entrypoints: list[str],
    output_dir: Path,
    data_files: list[str] | None = None,
    research_question: str = "",
) -> dict:
    command_info = benchmark_command(repo_path, entrypoints, research_question)
    generated_script = None
    command_cwd = repo_path
    if command_info:
        command, command_cwd = command_info
    else:
        generated_script = generated_replication_script(repo_path, data_files or [])
        command = [sys.executable, generated_script.name]
        command_cwd = repo_path

    if os.getenv("ALLOW_BENCHMARK_CODE_EXECUTION", "").lower() != "true":
        return {
            "executed": False,
            "command_ready": command,
            "command_cwd": str(command_cwd),
            "generated_script": str(generated_script) if generated_script else None,
            "reason": "Repo code execution is disabled. Set ALLOW_BENCHMARK_CODE_EXECUTION=true to run benchmark entrypoints.",
        }

    branch_result = prepare_replication_branch(repo_path)
    if not branch_result.get("branch_prepared"):
        return {
            "executed": False,
            "branch": branch_result,
            "reason": "Could not prepare isolated replication branch.",
        }

    try:
        completed = subprocess.run(
            command,
            cwd=command_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600,
        )
        (output_dir / "benchmark_stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (output_dir / "benchmark_stderr.txt").write_text(completed.stderr, encoding="utf-8")
        fallback_result = None
        if completed.returncode != 0 and generated_script is None and data_files:
            fallback_script = generated_replication_script(repo_path, data_files)
            fallback_command = [sys.executable, fallback_script.name]
            fallback_completed = subprocess.run(
                fallback_command,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=600,
            )
            (output_dir / "fallback_stdout.txt").write_text(fallback_completed.stdout, encoding="utf-8")
            (output_dir / "fallback_stderr.txt").write_text(fallback_completed.stderr, encoding="utf-8")
            fallback_result = {
                "executed": True,
                "command": fallback_command,
                "command_cwd": str(repo_path),
                "returncode": fallback_completed.returncode,
                "stdout_path": str(output_dir / "fallback_stdout.txt"),
                "stderr_path": str(output_dir / "fallback_stderr.txt"),
                "generated_script": str(fallback_script),
                "reason": "Original benchmark command failed, so Experiment ran a generated tabular fallback on repo data files.",
            }
        return {
            "executed": True,
            "branch": branch_result,
            "command": command,
            "command_cwd": str(command_cwd),
            "returncode": completed.returncode,
            "stdout_path": str(output_dir / "benchmark_stdout.txt"),
            "stderr_path": str(output_dir / "benchmark_stderr.txt"),
            "generated_script": str(generated_script) if generated_script else None,
            "fallback_result": fallback_result,
        }
    except Exception as exc:
        return {"executed": False, "branch": branch_result, "reason": str(exc), "command": command, "command_cwd": str(command_cwd)}


def build_replication_plan(spec: dict) -> list[str]:
    return [
        "Verify the cloned repository files, README, dependencies, benchmark scripts, and dataset instructions.",
        "Use the repository's original dataset, variables/features, train/test split, and reported benchmark metrics when available.",
        "Replicate the original benchmark first without modifying data or variables.",
        "Run the new hypothesis comparison by adding one transparent extra comparison factor while preserving the old dataset and variables.",
        "Compare original benchmark metrics against the modified replication metrics.",
        "Report whether the new hypothesis is supported, unsupported, or undetermined.",
    ]


def run_experiment_stage(
    proposal_input: str | Path,
    output_dir: str | Path = "paper_runs/latest/experiment",
) -> str:
    print("\n[Experiment Agent] Preparing benchmark replication...")
    proposal = read_text_or_path(proposal_input)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        spec = extract_execution_spec(proposal)
    except Exception as exc:
        spec = {"runner_type": "BENCHMARK_REPLICATION", "error": str(exc)}

    repo_path = Path(str(spec.get("local_repo_path", "")))
    entrypoints = [str(item) for item in spec.get("benchmark_entrypoints", [])]
    local_dataset_paths = [str(item) for item in spec.get("local_dataset_paths", [])]
    repo_exists = repo_path.exists()
    datasets_found = list_existing(local_dataset_paths)
    repo_data_files = list_existing([str(repo_path / item) for item in spec.get("repo_data_files", [])]) if repo_exists else []
    generated_data_files = [
        str(Path(path).relative_to(repo_path)) if repo_exists and Path(path).is_relative_to(repo_path) else str(path)
        for path in [*repo_data_files, *datasets_found]
    ]

    run_result = (
        safe_run_benchmark(
            repo_path,
            entrypoints,
            output_path,
            generated_data_files,
            research_question=str(spec.get("research_question", "")),
        )
        if repo_exists
        else {"executed": False, "reason": "Cloned repository path does not exist."}
    )

    has_data = bool(datasets_found or repo_data_files)
    has_entrypoints = bool(entrypoints)
    if not repo_exists:
        status = "REPLICATION_NEEDS_REDESIGN"
    elif has_entrypoints and has_data:
        status = "REPLICATION_READY"
    elif has_data:
        status = "REPLICATION_READY_WITH_GENERATED_SCRIPT"
    elif has_entrypoints:
        status = "REPLICATION_NEEDS_DATA"
    else:
        status = "REPLICATION_NEEDS_REDESIGN"
    result = {
        "status": status,
        "hypothesis_supported": "UNDETERMINED",
        "redesign_needed": status != "REPLICATION_READY",
        "runner_type": spec.get("runner_type", "BENCHMARK_REPLICATION"),
        "repo_path": str(repo_path),
        "repo_exists": repo_exists,
        "benchmark_entrypoints": entrypoints,
        "datasets_found": datasets_found,
        "repo_data_files_found": repo_data_files[:20],
        "metrics": spec.get("metrics", []),
        "new_hypothesis": spec.get("new_hypothesis", "TO_VERIFY"),
        "replication_plan": build_replication_plan(spec),
        "run_result": run_result,
        "limitations": [
            "Arbitrary benchmark repo code is not executed unless ALLOW_BENCHMARK_CODE_EXECUTION=true.",
            "Dependency installation is not automatic.",
            "If the repository does not include direct data files or clear dataset instructions, the benchmark must be completed manually or with a repo-specific runner.",
        ],
    }
    (output_path / "experiment_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    markdown = f"""# Experiment Results

## Status
{status}

## Hypothesis Supported
UNDETERMINED

## Summary
Prepared a benchmark-replication experiment from the selected GitHub repository and dataset sources. The original benchmark should be replicated first, then compared against the new hypothesis while preserving the old dataset, variables, and metrics.

## Repository
- Path: {repo_path}
- Exists: {repo_exists}

## Dataset
- Downloaded dataset files: {len(datasets_found)}
- Repository data files found: {len(repo_data_files)}

## Benchmark Entrypoints
{chr(10).join(f"- {item}" for item in entrypoints) if entrypoints else "- TO_IDENTIFY"}

## Metrics
{chr(10).join(f"- {item}" for item in spec.get("metrics", [])) if spec.get("metrics") else "- TO_IDENTIFY"}

## New Hypothesis
{spec.get("new_hypothesis", "TO_VERIFY")}

## Replication Plan
{chr(10).join(f"- {item}" for item in result["replication_plan"])}

## Execution
{json.dumps(run_result, indent=2)}

## Branch Safety
If benchmark execution is enabled, the cloned repository is checked out to a local branch before running code. Default branch name: `autoresearch-replication`. Override with `BENCHMARK_REPLICATION_BRANCH`.
"""
    (output_path / "experiment_output.md").write_text(markdown, encoding="utf-8")
    return markdown


if __name__ == "__main__":
    proposal_path = input("Enter proposal path or paste proposal text: ")
    print(run_experiment_stage(proposal_path))
