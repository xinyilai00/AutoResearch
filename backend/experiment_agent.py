from __future__ import annotations

import csv
import json
import math
import re
import statistics
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ExperimentResult:
    status: str
    hypothesis_supported: str
    redesign_needed: bool
    summary: str
    dataset_name: str
    dataset_url: str
    task_type: str
    target_column: str
    baseline: str
    metrics: dict
    results: dict
    limitations: list[str]
    output_files: list[str]


def read_text_or_path(value: str | Path) -> str:
    path = Path(value)
    if path.exists():
        return path.read_text(encoding="utf-8")
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


def needs_redesign(spec: dict) -> str | None:
    required = ["task_type", "dataset_url", "target_column", "success_metric"]
    for key in required:
        value = spec.get(key)
        if not value or str(value).strip().upper() == "TO_VERIFY":
            return f"Execution spec field '{key}' is missing or TO_VERIFY."

    dataset_url = str(spec.get("dataset_url", "")).strip()
    if not (dataset_url.startswith("http://") or dataset_url.startswith("https://") or Path(dataset_url).exists()):
        return "dataset_url must be a direct HTTP(S) CSV URL or an existing local file path."

    if dataset_url.startswith("http") and not looks_like_csv_url(dataset_url):
        return "dataset_url must point directly to a downloadable CSV file, not a repository or webpage."

    task_type = str(spec.get("task_type", "")).lower()
    if task_type not in {"classification", "regression"}:
        return "task_type must be classification or regression."

    return None


def looks_like_csv_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.path.lower().endswith(".csv") or "raw.githubusercontent.com" in parsed.netloc


def load_csv(spec: dict, output_dir: Path) -> tuple[list[dict], Path]:
    dataset_url = str(spec["dataset_url"]).strip()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "dataset.csv"

    if dataset_url.startswith("http://") or dataset_url.startswith("https://"):
        with urllib.request.urlopen(dataset_url, timeout=120) as response:
            data = response.read()
        data_path.write_bytes(data)
    else:
        source_path = Path(dataset_url)
        data_path.write_bytes(source_path.read_bytes())

    with data_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader]

    if not rows:
        raise ValueError("Dataset CSV loaded but has no rows.")
    return rows, data_path


def numeric_value(value: object) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def train_test_split(rows: list[dict], test_fraction: float = 0.2) -> tuple[list[dict], list[dict]]:
    split_index = max(1, int(len(rows) * (1 - test_fraction)))
    return rows[:split_index], rows[split_index:] or rows[:]


def run_classification(rows: list[dict], target_column: str) -> tuple[dict, dict]:
    train_rows, test_rows = train_test_split(rows)
    labels = [row.get(target_column, "") for row in train_rows if row.get(target_column, "") != ""]
    if not labels:
        raise ValueError("Target column has no usable labels.")

    majority_label = max(set(labels), key=labels.count)
    test_labels = [row.get(target_column, "") for row in test_rows if row.get(target_column, "") != ""]
    if not test_labels:
        raise ValueError("Test split has no usable labels.")

    correct = sum(1 for label in test_labels if label == majority_label)
    accuracy = correct / len(test_labels)
    metrics = {
        "accuracy": accuracy,
        "test_examples": len(test_labels),
    }
    results = {
        "baseline_prediction": majority_label,
        "correct_predictions": correct,
    }
    return metrics, results


def run_regression(rows: list[dict], target_column: str) -> tuple[dict, dict]:
    train_rows, test_rows = train_test_split(rows)
    train_values = [numeric_value(row.get(target_column)) for row in train_rows]
    train_values = [value for value in train_values if value is not None]
    if not train_values:
        raise ValueError("Target column has no usable numeric training values.")

    prediction = statistics.mean(train_values)
    actual_values = [numeric_value(row.get(target_column)) for row in test_rows]
    actual_values = [value for value in actual_values if value is not None]
    if not actual_values:
        raise ValueError("Test split has no usable numeric target values.")

    errors = [actual - prediction for actual in actual_values]
    absolute_errors = [abs(error) for error in errors]
    squared_errors = [error * error for error in errors]
    mae = statistics.mean(absolute_errors)
    rmse = math.sqrt(statistics.mean(squared_errors))

    mean_actual = statistics.mean(actual_values)
    total_sum_squares = sum((actual - mean_actual) ** 2 for actual in actual_values)
    residual_sum_squares = sum(squared_errors)
    r2 = 1 - residual_sum_squares / total_sum_squares if total_sum_squares else 0.0

    metrics = {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "test_examples": len(actual_values),
    }
    results = {
        "baseline_prediction": prediction,
    }
    return metrics, results


def decide_hypothesis_support(spec: dict, metrics: dict) -> str:
    metric_name = str(spec.get("success_metric", "")).lower()
    direction = str(spec.get("threshold_direction", "")).lower()
    try:
        threshold = float(spec.get("success_threshold"))
    except (TypeError, ValueError):
        return "INCONCLUSIVE"

    if metric_name not in metrics:
        return "INCONCLUSIVE"

    value = float(metrics[metric_name])
    if direction == "greater_or_equal":
        return "SUPPORTED" if value >= threshold else "NOT_SUPPORTED"
    if direction == "less_or_equal":
        return "SUPPORTED" if value <= threshold else "NOT_SUPPORTED"
    return "INCONCLUSIVE"


def write_outputs(output_dir: Path, result: ExperimentResult) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "experiment_result.json"
    markdown_path = output_dir / "experiment_output.md"
    json_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    lines = [
        "# Experiment Results",
        "",
        "## Status",
        result.status,
        "",
        "## Hypothesis Supported",
        result.hypothesis_supported,
        "",
        "## Summary",
        result.summary,
        "",
        "## Dataset",
        f"- Name: {result.dataset_name}",
        f"- URL/path: {result.dataset_url}",
        f"- Target column: {result.target_column}",
        "",
        "## Method",
        f"- Task type: {result.task_type}",
        f"- Baseline: {result.baseline}",
        "",
        "## Metrics",
        *[f"- {key}: {value}" for key, value in result.metrics.items()],
        "",
        "## Results",
        *[f"- {key}: {value}" for key, value in result.results.items()],
        "",
        "## Limitations",
        *[f"- {item}" for item in result.limitations],
        "",
        "## Output Files",
        *[f"- {item}" for item in result.output_files],
    ]
    markdown = "\n".join(lines).rstrip() + "\n"
    markdown_path.write_text(markdown, encoding="utf-8")
    return markdown


def redesign_result(proposal: str, output_dir: Path, reason: str) -> str:
    result = ExperimentResult(
        status="REDESIGN_NEEDED",
        hypothesis_supported="UNDETERMINED",
        redesign_needed=True,
        summary=f"Experiment was not executed: {reason}",
        dataset_name="TO_VERIFY",
        dataset_url="TO_VERIFY",
        task_type="TO_VERIFY",
        target_column="TO_VERIFY",
        baseline="TO_VERIFY",
        metrics={},
        results={},
        limitations=[
            "No empirical results were generated.",
            "Proposal must provide a direct downloadable/local CSV dataset and executable task settings.",
        ],
        output_files=[],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "proposal_needs_redesign.md").write_text(
        "# Proposal Needs Redesign\n\n"
        f"Reason: {reason}\n\n"
        "Original proposal:\n\n"
        f"{proposal.rstrip()}\n",
        encoding="utf-8",
    )
    return write_outputs(output_dir, result)


def run_experiment_stage(
    proposal_input: str | Path,
    output_dir: str | Path = "paper_runs/latest/experiment",
) -> str:
    print("\n[Experiment Agent] Running experiment from proposal...")
    proposal = read_text_or_path(proposal_input)
    output_path = Path(output_dir)

    try:
        spec = extract_execution_spec(proposal)
    except Exception as exc:
        return redesign_result(proposal, output_path, str(exc))

    redesign_reason = needs_redesign(spec)
    if redesign_reason:
        return redesign_result(proposal, output_path, redesign_reason)

    try:
        rows, data_path = load_csv(spec, output_path)
        target_column = str(spec["target_column"]).strip()
        if target_column not in rows[0]:
            raise ValueError(f"Target column '{target_column}' does not exist in the CSV header.")

        task_type = str(spec["task_type"]).lower()
        if task_type == "classification":
            metrics, results = run_classification(rows, target_column)
        else:
            metrics, results = run_regression(rows, target_column)

        hypothesis_supported = decide_hypothesis_support(spec, metrics)
        result = ExperimentResult(
            status="COMPLETED",
            hypothesis_supported=hypothesis_supported,
            redesign_needed=False,
            summary=(
                "Experiment completed using the executable proposal spec. "
                "Results are produced from the loaded dataset and baseline evaluation."
            ),
            dataset_name=str(spec.get("dataset_name", "Unknown")),
            dataset_url=str(spec.get("dataset_url", "")),
            task_type=task_type,
            target_column=target_column,
            baseline=str(spec.get("baseline", "")),
            metrics=metrics,
            results=results,
            limitations=[
                "This initial Experiment Agent supports CSV classification/regression baselines only.",
                "More advanced models require a dedicated safe runner.",
            ],
            output_files=[str(data_path), str(output_path / "experiment_result.json"), str(output_path / "experiment_output.md")],
        )
        return write_outputs(output_path, result)
    except Exception as exc:
        return redesign_result(proposal, output_path, str(exc))


if __name__ == "__main__":
    proposal_path = input("Enter proposal path or paste proposal text: ")
    print(run_experiment_stage(proposal_path))
