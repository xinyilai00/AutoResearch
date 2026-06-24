from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import re
import statistics
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    runner_type: str
    task_type: str
    target_column: str
    baseline: str
    metrics: dict
    results: dict
    limitations: list[str]
    output_files: list[str]


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


def run_parallel_experiment_agents(spec: dict, proposal: str, output_dir: Path) -> dict:
    try:
        try:
            from .experiment.data_agent import run_data_agent
            from .experiment.schema_agent import run_schema_agent
            from .experiment.method_agent import run_method_agent
            from .experiment.risk_agent import run_risk_agent
        except ImportError:
            from experiment.data_agent import run_data_agent
            from experiment.schema_agent import run_schema_agent
            from experiment.method_agent import run_method_agent
            from experiment.risk_agent import run_risk_agent

        checks = {}
        agents = {
            "data": run_data_agent,
            "schema": run_schema_agent,
            "method": run_method_agent,
            "risk": run_risk_agent,
        }
        print("[Experiment Agent] Running experiment check agents in parallel...")
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            future_to_name = {
                executor.submit(agent_fn, spec, proposal): name
                for name, agent_fn in agents.items()
            }
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    checks[name] = future.result()
                except Exception as exc:
                    checks[name] = {
                        "agent": name,
                        "ready": False,
                        "issues": [str(exc)],
                    }

        report = {
            "ready": all(bool(check.get("ready")) for check in checks.values()),
            "checks": checks,
        }
        if os.getenv("WRITE_EXPERIMENT_CHECKS", "").lower() == "true":
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "experiment_agent_checks.json").write_text(
                json.dumps(report, indent=2),
                encoding="utf-8",
            )
        return report
    except Exception as exc:
        return {
            "ready": False,
            "checks": {
                "parallel_agents": {
                    "agent": "parallel_agents",
                    "ready": False,
                    "issues": [str(exc)],
                }
            },
        }


SUPPORTED_RUNNER_TYPES = {
    "universal_tabular_csv",
    "direct_csv",
    "multi_csv",
    "universal_data_file",
    "financial_sentiment_timeseries",
}
SUPPORTED_TASK_TYPES = {"classification", "regression", "auto", "inspect"}
SUPPORTED_METRICS = {"accuracy", "mae", "rmse", "r2", "none", "inspect"}
SUPPORTED_DATA_EXTENSIONS = {".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".zip"}
NON_DATA_FILE_MARKERS = (
    ".babelrc",
    ".claude/",
    ".editorconfig",
    ".eslintrc",
    ".github/",
    ".gitignore",
    ".markdownlint",
    ".prettierrc",
    "cargo.lock",
    "composer.lock",
    "config/",
    "eslint.config",
    "flake.lock",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pyproject.toml",
    "requirements.txt",
    "settings.json",
    "tsconfig",
    "yarn.lock",
)


def needs_redesign(spec: dict) -> str | None:
    runner_type = str(spec.get("runner_type", "universal_tabular_csv")).lower()
    if runner_type == "needs_new_runner":
        return "Proposal says this experiment requires a new specialized runner."
    if runner_type not in SUPPORTED_RUNNER_TYPES:
        return f"runner_type '{runner_type}' is not supported by the current Experiment Agent."

    task_type = str(spec.get("task_type", "")).lower()
    workflow_runner = runner_type == "financial_sentiment_timeseries"
    inspect_only = runner_type == "universal_data_file" and task_type == "inspect"
    if workflow_runner:
        required = ["task_type", "target_column", "success_metric"]
        for key in required:
            value = spec.get(key)
            if not value or str(value).strip().upper() == "TO_VERIFY":
                return f"Execution spec field '{key}' is missing or TO_VERIFY."
        if task_type not in {"regression", "auto"}:
            return "financial_sentiment_timeseries supports regression or auto task_type."
        return None

    required = ["task_type", "success_metric"] if inspect_only else ["task_type", "target_column", "success_metric"]
    for key in required:
        value = spec.get(key)
        if not value or str(value).strip().upper() == "TO_VERIFY":
            return f"Execution spec field '{key}' is missing or TO_VERIFY."

    dataset_urls = dataset_urls_from_spec(spec)
    if not dataset_urls:
        return "Execution spec must provide dataset_url or dataset_urls."

    for dataset_url in dataset_urls:
        if dataset_url.upper() == "TO_VERIFY":
            return "dataset_urls contains TO_VERIFY."
        if not (dataset_url.startswith("http://") or dataset_url.startswith("https://") or Path(dataset_url).exists()):
            return "Each dataset URL must be a direct HTTP(S) data file URL or an existing local file path."
        if runner_type in {"universal_tabular_csv", "direct_csv", "multi_csv"} and dataset_url.startswith("http") and not looks_like_csv_url(dataset_url):
            return "Each HTTP dataset URL must point directly to a downloadable CSV file, not a repository or webpage."
        if runner_type == "universal_data_file" and not looks_like_supported_data_file(dataset_url):
            return "universal_data_file supports direct CSV, TSV, JSON, JSONL, NDJSON, or ZIP files only."

    if task_type not in SUPPORTED_TASK_TYPES:
        return "task_type must be classification, regression, or auto."

    metric_name = str(spec.get("success_metric", "")).lower()
    if metric_name not in SUPPORTED_METRICS:
        return f"success_metric '{metric_name}' is not supported by the current Experiment Agent."

    return None


def looks_like_csv_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    return path.endswith(".csv")


def looks_like_supported_data_file(url_or_path: str) -> bool:
    parsed = urllib.parse.urlparse(url_or_path)
    path = parsed.path.lower()
    suffix = Path(path).suffix
    if suffix not in SUPPORTED_DATA_EXTENSIONS:
        return False
    if any(marker in path for marker in NON_DATA_FILE_MARKERS):
        return False
    name = path.rsplit("/", 1)[-1]
    return not name.startswith(".")


def dataset_urls_from_spec(spec: dict) -> list[str]:
    urls = []
    raw_urls = spec.get("dataset_urls")
    if isinstance(raw_urls, list):
        urls.extend(str(url).strip() for url in raw_urls if str(url).strip())
    dataset_url = str(spec.get("dataset_url", "")).strip()
    if dataset_url and dataset_url.upper() != "TO_VERIFY":
        urls.insert(0, dataset_url)
    return list(dict.fromkeys(urls))


def load_csvs(spec: dict, output_dir: Path) -> tuple[list[dict], list[Path]]:
    dataset_urls = dataset_urls_from_spec(spec)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    data_paths = []
    failures = []

    for index, dataset_url in enumerate(dataset_urls, 1):
        data_path = output_dir / f"dataset_{index:02d}.csv"
        try:
            if dataset_url.startswith("http://") or dataset_url.startswith("https://"):
                with urllib.request.urlopen(dataset_url, timeout=120) as response:
                    data = response.read()
                data_path.write_bytes(data)
            else:
                source_path = Path(dataset_url)
                data_path.write_bytes(source_path.read_bytes())
        except Exception as exc:
            failures.append(f"{dataset_url}: {exc}")
            continue

        with data_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [dict(row, source_file=data_path.name) for row in reader]
        all_rows.extend(rows)
        data_paths.append(data_path)

    if not all_rows:
        if failures:
            raise ValueError("No CSV datasets could be loaded. Failures: " + " | ".join(failures[:5]))
        raise ValueError("Dataset CSV loaded but has no rows.")
    return all_rows, data_paths


def filename_from_dataset_url(dataset_url: str, index: int) -> str:
    parsed = urllib.parse.urlparse(dataset_url)
    name = Path(parsed.path).name
    if not name:
        name = f"dataset_{index:02d}.dat"
    return f"dataset_{index:02d}_{name}"


def download_data_files(spec: dict, output_dir: Path) -> list[Path]:
    dataset_urls = dataset_urls_from_spec(spec)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_paths = []
    failures = []

    for index, dataset_url in enumerate(dataset_urls, 1):
        data_path = output_dir / filename_from_dataset_url(dataset_url, index)
        try:
            if dataset_url.startswith("http://") or dataset_url.startswith("https://"):
                with urllib.request.urlopen(dataset_url, timeout=120) as response:
                    data = response.read()
                data_path.write_bytes(data)
            else:
                source_path = Path(dataset_url)
                data_path.write_bytes(source_path.read_bytes())
        except Exception as exc:
            failures.append(f"{dataset_url}: {exc}")
            continue
        data_paths.append(data_path)

    if not data_paths and failures:
        raise ValueError("No data files could be downloaded or loaded. Failures: " + " | ".join(failures[:5]))
    return data_paths


def read_delimited_rows(path: Path, delimiter: str | None = None) -> list[dict]:
    if delimiter is None:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return [dict(row, source_file=path.name) for row in reader]


def json_to_rows(payload: object, source_name: str) -> list[dict]:
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return [dict(item, source_file=source_name) for item in payload]
        return [{"value": item, "source_file": source_name} for item in payload]
    if isinstance(payload, dict):
        values = list(payload.values())
        if values and all(isinstance(item, dict) for item in values):
            return [dict(item, source_file=source_name) for item in values]
        return [{**payload, "source_file": source_name}]
    return [{"value": payload, "source_file": source_name}]


def read_json_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return json_to_rows(payload, path.name)


def read_jsonl_rows(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(dict(payload, source_file=path.name))
            else:
                rows.append({"value": payload, "line_number": line_number, "source_file": path.name})
    return rows


def load_supported_data_file(path: Path, output_dir: Path) -> tuple[list[dict], list[Path], list[dict]]:
    suffix = path.suffix.lower()
    loaded_paths = [path]
    inventories = []

    if suffix == ".zip":
        extract_dir = output_dir / f"{path.stem}_extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        all_rows = []
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                member_suffix = Path(member).suffix.lower()
                if member.endswith("/") or member_suffix not in SUPPORTED_DATA_EXTENSIONS - {".zip"}:
                    continue
                safe_name = Path(member).name
                extracted_path = extract_dir / safe_name
                extracted_path.write_bytes(archive.read(member))
                rows, child_paths, child_inventory = load_supported_data_file(extracted_path, output_dir)
                all_rows.extend(rows)
                loaded_paths.extend(child_paths)
                inventories.extend(child_inventory)
        inventories.insert(
            0,
            {
                "file": str(path),
                "type": "zip",
                "members_loaded": len(loaded_paths) - 1,
                "rows": len(all_rows),
            },
        )
        return all_rows, loaded_paths, inventories

    if suffix == ".csv":
        rows = read_delimited_rows(path, ",")
        file_type = "csv"
    elif suffix == ".tsv":
        rows = read_delimited_rows(path, "\t")
        file_type = "tsv"
    elif suffix in {".jsonl", ".ndjson"}:
        rows = read_jsonl_rows(path)
        file_type = "jsonl"
    elif suffix == ".json":
        rows = read_json_rows(path)
        file_type = "json"
    else:
        rows = []
        file_type = suffix.lstrip(".") or "unknown"

    columns = sorted({key for row in rows[:100] for key in row.keys()})
    inventories.append(
        {
            "file": str(path),
            "type": file_type,
            "rows": len(rows),
            "columns": columns[:50],
            "column_count": len(columns),
        }
    )
    return rows, loaded_paths, inventories


def load_universal_data_files(spec: dict, output_dir: Path) -> tuple[list[dict], list[Path], list[dict]]:
    downloaded_paths = download_data_files(spec, output_dir)
    all_rows = []
    loaded_paths = []
    inventory = []

    for path in downloaded_paths:
        rows, paths, file_inventory = load_supported_data_file(path, output_dir)
        all_rows.extend(rows)
        loaded_paths.extend(paths)
        inventory.extend(file_inventory)

    return all_rows, loaded_paths, inventory


def infer_target_column(rows: list[dict]) -> str:
    if not rows:
        raise ValueError("Cannot infer target column from an empty dataset.")
    columns = [column for column in rows[0].keys() if column != "source_file"]
    if not columns:
        raise ValueError("Cannot infer target column because the CSV has no usable columns.")

    preferred_names = [
        "injury",
        "injured",
        "injury_label",
        "injury_status",
        "injury_next_7d",
        "target_injury_next_7d",
        "injured_next_week",
        "injured_next_7d",
        "is_injured",
        "target",
        "label",
        "class",
        "category",
        "outcome",
        "result",
        "ftr",
        "full_time_result",
        "y",
    ]
    normalized_columns = {
        re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_"): column
        for column in columns
    }
    for preferred_name in preferred_names:
        if preferred_name in normalized_columns:
            return normalized_columns[preferred_name]

    usable_columns = []
    for column in columns:
        values = [row.get(column, "") for row in rows[:500] if str(row.get(column, "")).strip()]
        if values:
            usable_columns.append((column, len(set(values))))
    if not usable_columns:
        raise ValueError("Cannot infer target column because all columns are empty.")

    categorical_candidates = [
        (column, unique_count)
        for column, unique_count in usable_columns
        if 1 < unique_count <= 50
    ]
    if categorical_candidates:
        return categorical_candidates[-1][0]
    return usable_columns[-1][0]


def infer_task_type(rows: list[dict], target_column: str, requested_task_type: str) -> str:
    task_type = requested_task_type.lower().strip()
    if task_type in {"classification", "regression"}:
        return task_type

    values = [row.get(target_column, "") for row in rows[:1000] if str(row.get(target_column, "")).strip()]
    if not values:
        raise ValueError(f"Cannot infer task type because target column '{target_column}' has no values.")

    numeric_values = [numeric_value(value) for value in values]
    numeric_values = [value for value in numeric_values if value is not None]
    unique_count = len(set(values))
    if len(numeric_values) == len(values) and unique_count > 20:
        return "regression"
    return "classification"


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
        f"- Runner type: {result.runner_type}",
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


def redesign_result(proposal: str, output_dir: Path, reason: str, spec: dict | None = None) -> str:
    spec = spec or {}
    dataset_url = ", ".join(dataset_urls_from_spec(spec)) if spec else "TO_VERIFY"
    limitations = [
        "No empirical results were generated.",
        "The current Experiment Agent can execute universal_tabular_csv and universal_data_file specs only.",
        "The proposal must be redesigned as an executable analysis over downloadable/public data files before this stage can run.",
    ]
    notes = str(spec.get("notes_for_experiment_agent", "")).strip()
    if notes:
        limitations.append(f"Runner notes: {notes}")

    result = ExperimentResult(
        status="REDESIGN_NEEDED",
        hypothesis_supported="UNDETERMINED",
        redesign_needed=True,
        summary=f"Experiment was not executed: {reason}",
        dataset_name=str(spec.get("dataset_name", "TO_VERIFY")),
        dataset_url=dataset_url or "TO_VERIFY",
        runner_type=str(spec.get("runner_type", "TO_VERIFY")),
        task_type=str(spec.get("task_type", "TO_VERIFY")),
        target_column=str(spec.get("target_column", "TO_VERIFY")),
        baseline=str(spec.get("baseline", "TO_VERIFY")),
        metrics={},
        results={},
        limitations=limitations,
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


def universal_inventory_result(
    spec: dict,
    output_dir: Path,
    rows: list[dict],
    data_paths: list[Path],
    inventory: list[dict],
    reason: str,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "data_inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    result = ExperimentResult(
        status="DATA_LOADED_REDESIGN_NEEDED",
        hypothesis_supported="UNDETERMINED",
        redesign_needed=True,
        summary=(
            "Universal data files were downloaded and inspected, but the full experiment was not executed: "
            f"{reason}"
        ),
        dataset_name=str(spec.get("dataset_name", "Unknown")),
        dataset_url=", ".join(dataset_urls_from_spec(spec)),
        runner_type=str(spec.get("runner_type", "universal_data_file")),
        task_type=str(spec.get("task_type", "inspect")),
        target_column=str(spec.get("target_column", "TO_VERIFY")),
        baseline=str(spec.get("baseline", "TO_VERIFY")),
        metrics={
            "files_loaded": len(data_paths),
            "tabular_rows_loaded": len(rows),
            "inventoried_files": len(inventory),
        },
        results={
            "inventory_path": str(inventory_path),
            "file_types": sorted({str(item.get("type")) for item in inventory}),
        },
        limitations=[
            "The universal_data_file runner loads and inspects common data files but does not perform scraping, API pagination, NLP extraction, graph construction, deep learning, or advanced statistical tests.",
            "Provide a direct target column and a supported task type to run a simple dataset analysis, or implement a specialized runner for the full proposed dataset analysis.",
        ],
        output_files=[*(str(path) for path in data_paths), str(inventory_path), str(output_dir / "experiment_result.json"), str(output_dir / "experiment_output.md")],
    )
    return write_outputs(output_dir, result)


def run_universal_data_file_experiment(spec: dict, output_path: Path) -> str:
    rows, data_paths, inventory = load_universal_data_files(spec, output_path)
    target_column = str(spec.get("target_column", "")).strip()
    task_type_requested = str(spec.get("task_type", "inspect")).lower()

    if not rows:
        return universal_inventory_result(
            spec,
            output_path,
            rows,
            data_paths,
            inventory,
            "No tabular rows could be extracted from the provided files.",
        )

    if target_column.upper() in {"", "TO_VERIFY", "AUTO_TARGET"}:
        try:
            target_column = infer_target_column(rows)
            spec = dict(spec)
            spec["target_column"] = target_column
            if task_type_requested == "inspect":
                task_type_requested = "auto"
                spec["task_type"] = "auto"
        except ValueError as exc:
            return universal_inventory_result(
                spec,
                output_path,
                rows,
                data_paths,
                inventory,
                f"Could not infer an executable target column: {exc}",
            )

    if task_type_requested == "inspect":
        return universal_inventory_result(
            spec,
            output_path,
            rows,
            data_paths,
            inventory,
            "Task type is inspect, so no baseline model was run.",
        )

    if target_column not in rows[0]:
        return universal_inventory_result(
            spec,
            output_path,
            rows,
            data_paths,
            inventory,
            f"Target column '{target_column}' does not exist in the loaded data.",
        )

    task_type = infer_task_type(rows, target_column, task_type_requested)
    if task_type == "classification":
        metrics, results = run_classification(rows, target_column)
    else:
        metrics, results = run_regression(rows, target_column)

    inventory_path = output_path / "data_inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    hypothesis_supported = decide_hypothesis_support(spec, metrics)
    result = ExperimentResult(
        status="COMPLETED",
        hypothesis_supported=hypothesis_supported,
        redesign_needed=False,
        summary=(
            "Experiment completed with the universal_data_file runner using extracted tabular rows "
            "and a simple baseline evaluation."
        ),
        dataset_name=str(spec.get("dataset_name", "Unknown")),
        dataset_url=", ".join(dataset_urls_from_spec(spec)),
        runner_type="universal_data_file",
        task_type=task_type,
        target_column=target_column,
        baseline=str(spec.get("baseline", "")),
        metrics=metrics,
        results=results | {"inventory_path": str(inventory_path)},
        limitations=[
            "The universal_data_file runner performs file loading and simple baseline evaluation only.",
            "Prompt-specific feature engineering, graph models, NLP extraction, scraping, and statistical tests require specialized runners.",
        ],
        output_files=[*(str(path) for path in data_paths), str(inventory_path), str(output_path / "experiment_result.json"), str(output_path / "experiment_output.md")],
    )
    return write_outputs(output_path, result)


POSITIVE_WORDS = {
    "beat",
    "beats",
    "bullish",
    "gain",
    "gains",
    "growth",
    "improve",
    "improved",
    "profit",
    "profits",
    "record",
    "rise",
    "rises",
    "strong",
    "surge",
    "up",
}
NEGATIVE_WORDS = {
    "bearish",
    "decline",
    "declines",
    "down",
    "drop",
    "drops",
    "fall",
    "falls",
    "loss",
    "losses",
    "miss",
    "misses",
    "risk",
    "risks",
    "weak",
    "warning",
}


def simple_financial_sentiment(text: str) -> float:
    words = re.findall(r"[A-Za-z]+", text.lower())
    if not words:
        return 0.0
    positive = sum(1 for word in words if word in POSITIVE_WORDS)
    negative = sum(1 for word in words if word in NEGATIVE_WORDS)
    return (positive - negative) / max(1, positive + negative)


def normalize_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return text[:10]


def parse_float(value: object) -> float | None:
    return numeric_value(value)


def find_column(row: dict, candidates: list[str]) -> str | None:
    normalized = {
        re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_"): key
        for key in row.keys()
    }
    for candidate in candidates:
        normalized_candidate = re.sub(r"[^a-z0-9]+", "_", candidate.lower()).strip("_")
        if normalized_candidate in normalized:
            return normalized[normalized_candidate]
    return None


def rows_from_direct_financial_files(spec: dict, output_path: Path) -> tuple[list[dict], list[dict], list[Path], list[dict]]:
    file_urls = [
        url
        for url in dataset_urls_from_spec(spec)
        if url.upper() != "TO_VERIFY" and looks_like_supported_data_file(url)
    ]
    if not file_urls:
        return [], [], [], []

    file_spec = dict(spec)
    file_spec["dataset_url"] = file_urls[0]
    file_spec["dataset_urls"] = file_urls
    rows, paths, inventory = load_universal_data_files(file_spec, output_path)

    price_rows = []
    headline_rows = []
    for row in rows:
        date_col = find_column(row, ["date", "datetime", "timestamp"])
        close_col = find_column(row, ["close", "adj close", "adj_close", "adjusted_close"])
        headline_col = find_column(row, ["headline", "title", "text", "article", "content"])
        if date_col and close_col:
            price_rows.append(row)
        elif date_col and headline_col:
            headline_rows.append(row)
    return price_rows, headline_rows, paths, inventory


def load_yfinance_price_rows(spec: dict, output_path: Path) -> tuple[list[dict], list[Path], list[str]]:
    tickers = spec.get("tickers") or spec.get("symbols") or ["AAPL", "MSFT", "GOOGL"]
    if isinstance(tickers, str):
        tickers = [item.strip() for item in re.split(r"[,;\\s]+", tickers) if item.strip()]
    start = str(spec.get("start_date") or "2021-01-01")
    end = str(spec.get("end_date") or "2024-12-31")
    warnings = []

    try:
        import yfinance as yf
    except Exception as exc:
        return [], [], [f"yfinance unavailable: {exc}"]

    rows = []
    paths = []
    for ticker in tickers[:10]:
        try:
            frame = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        except Exception as exc:
            warnings.append(f"yfinance failed for {ticker}: {exc}")
            continue
        if frame is None or frame.empty:
            warnings.append(f"yfinance returned no rows for {ticker}.")
            continue

        csv_path = output_path / f"yfinance_{ticker}.csv"
        try:
            frame.to_csv(csv_path)
            paths.append(csv_path)
        except Exception:
            pass

        previous_close = None
        for index, record in frame.reset_index().iterrows():
            close_value = float(record.get("Close"))
            date_value = record.get("Date")
            if previous_close and previous_close > 0:
                daily_log_return = math.log(close_value / previous_close)
            else:
                daily_log_return = 0.0
            rows.append(
                {
                    "ticker": ticker,
                    "date": str(date_value)[:10],
                    "close": close_value,
                    "daily_log_return": daily_log_return,
                    "volume": float(record.get("Volume") or 0),
                }
            )
            previous_close = close_value
    return rows, paths, warnings


def add_next_day_target(price_rows: list[dict], target_column: str) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in price_rows:
        ticker = str(row.get("ticker") or "UNKNOWN")
        grouped.setdefault(ticker, []).append(row)

    output_rows = []
    for ticker_rows in grouped.values():
        ticker_rows = sorted(ticker_rows, key=lambda row: str(row.get("date", "")))
        for index, row in enumerate(ticker_rows[:-1]):
            current_close = parse_float(row.get("close"))
            next_close = parse_float(ticker_rows[index + 1].get("close"))
            if current_close and next_close and current_close > 0:
                row[target_column] = math.log(next_close / current_close)
                output_rows.append(row)
    return output_rows


def aggregate_headline_sentiment(headline_rows: list[dict]) -> dict[tuple[str, str], dict]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in headline_rows:
        if not row:
            continue
        date_col = find_column(row, ["date", "datetime", "timestamp"])
        text_col = find_column(row, ["headline", "title", "text", "article", "content"])
        ticker_col = find_column(row, ["ticker", "symbol", "stock"])
        if not date_col or not text_col:
            continue
        date_value = normalize_date(row.get(date_col))
        ticker = str(row.get(ticker_col) or "MARKET").upper()
        grouped.setdefault((ticker, date_value), []).append(simple_financial_sentiment(str(row.get(text_col))))

    features = {}
    for key, values in grouped.items():
        features[key] = {
            "sentiment_mean": statistics.mean(values),
            "sentiment_disagreement": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "headline_count": len(values),
        }
    return features


def merge_sentiment_features(price_rows: list[dict], headline_rows: list[dict]) -> list[dict]:
    sentiment_by_key = aggregate_headline_sentiment(headline_rows)
    merged = []
    for row in price_rows:
        ticker = str(row.get("ticker") or "MARKET").upper()
        date_value = normalize_date(row.get("date"))
        sentiment = sentiment_by_key.get((ticker, date_value)) or sentiment_by_key.get(("MARKET", date_value)) or {}
        merged_row = dict(row)
        merged_row["sentiment_mean"] = sentiment.get("sentiment_mean", 0.0)
        merged_row["sentiment_disagreement"] = sentiment.get("sentiment_disagreement", 0.0)
        merged_row["headline_count"] = sentiment.get("headline_count", 0)
        merged.append(merged_row)
    return merged


def run_financial_sentiment_timeseries_experiment(spec: dict, output_path: Path) -> str:
    output_path.mkdir(parents=True, exist_ok=True)
    target_column = str(spec.get("target_column") or "next_day_log_return")
    warnings = []
    output_files = []

    price_rows, headline_rows, data_paths, inventory = rows_from_direct_financial_files(spec, output_path)
    output_files.extend(str(path) for path in data_paths)

    if not price_rows:
        yf_rows, yf_paths, yf_warnings = load_yfinance_price_rows(spec, output_path)
        price_rows.extend(yf_rows)
        output_files.extend(str(path) for path in yf_paths)
        warnings.extend(yf_warnings)

    if not headline_rows:
        warnings.append("No direct headline dataset was loaded. Kaggle/Hugging Face dataset pages require manual download, direct file URLs, or credentials.")

    if not price_rows:
        result = ExperimentResult(
            status="DATA_LOADED_REDESIGN_NEEDED",
            hypothesis_supported="UNDETERMINED",
            redesign_needed=True,
            summary=(
                "financial_sentiment_timeseries could not run because no usable OHLCV price rows were loaded. "
                "Provide a direct local/HTTP price CSV or install/configure yfinance with network access."
            ),
            dataset_name=str(spec.get("dataset_name", "Financial sentiment time series")),
            dataset_url=", ".join(dataset_urls_from_spec(spec)),
            runner_type="financial_sentiment_timeseries",
            task_type=str(spec.get("task_type", "regression")),
            target_column=target_column,
            baseline=str(spec.get("baseline", "mean_prediction")),
            metrics={"direct_files_loaded": len(data_paths), "inventoried_files": len(inventory)},
            results={"warnings": warnings},
            limitations=[
                "This workflow runner supports local/direct OHLCV files or optional yfinance downloads.",
                "Kaggle pages, FinBERT inference, LSTM/Transformer training, and Diebold-Mariano tests require extra dependencies and credentials.",
            ],
            output_files=output_files,
        )
        return write_outputs(output_path, result)

    price_rows = add_next_day_target(price_rows, target_column)
    merged_rows = merge_sentiment_features(price_rows, headline_rows)
    merged_path = output_path / "financial_sentiment_panel.csv"
    if merged_rows:
        with merged_path.open("w", encoding="utf-8", newline="") as handle:
            fieldnames = sorted({key for row in merged_rows for key in row.keys()})
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merged_rows)
        output_files.append(str(merged_path))

    if not merged_rows:
        raise ValueError("No rows remained after next-day target construction.")

    metrics, results = run_regression(merged_rows, target_column)
    hypothesis_supported = decide_hypothesis_support(spec, metrics)
    result = ExperimentResult(
        status="COMPLETED",
        hypothesis_supported=hypothesis_supported,
        redesign_needed=False,
        summary=(
            "financial_sentiment_timeseries completed a runnable baseline using available OHLCV rows "
            "and lightweight sentiment features when headline rows were available."
        ),
        dataset_name=str(spec.get("dataset_name", "Financial sentiment time series")),
        dataset_url=", ".join(dataset_urls_from_spec(spec)),
        runner_type="financial_sentiment_timeseries",
        task_type="regression",
        target_column=target_column,
        baseline=str(spec.get("baseline", "mean_prediction")),
        metrics=metrics | {
            "price_rows": len(price_rows),
            "headline_rows": len(headline_rows),
            "panel_rows": len(merged_rows),
        },
        results=results | {"warnings": warnings},
        limitations=[
            "This runner currently executes a safe baseline, not full LSTM/Transformer training.",
            "FinBERT is represented by a lightweight lexical sentiment fallback unless a future transformer inference module is added.",
            "Kaggle dataset pages require credentials or direct downloaded files.",
            "Diebold-Mariano tests and regime-stratified analysis are not implemented in this safe baseline runner yet.",
        ],
        output_files=[*output_files, str(output_path / "experiment_result.json"), str(output_path / "experiment_output.md")],
    )
    return write_outputs(output_path, result)


def inspect_available_files_for_redesign(spec: dict, output_path: Path, reason: str) -> str | None:
    readable_urls = [
        url
        for url in dataset_urls_from_spec(spec)
        if url.upper() != "TO_VERIFY"
        and (
            (url.startswith("http://") or url.startswith("https://") or Path(url).exists())
            and looks_like_supported_data_file(url)
        )
    ]
    if not readable_urls:
        return None

    inspect_spec = dict(spec)
    inspect_spec.update(
        {
            "runner_type": "universal_data_file",
            "task_type": "inspect",
            "dataset_url": readable_urls[0],
            "dataset_urls": readable_urls,
            "success_metric": "inspect",
        }
    )
    try:
        rows, data_paths, inventory = load_universal_data_files(inspect_spec, output_path)
    except Exception:
        return None

    return universal_inventory_result(
        inspect_spec,
        output_path,
        rows,
        data_paths,
        inventory,
        reason,
    )



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

    run_parallel_experiment_agents(spec, proposal, output_path)

    redesign_reason = needs_redesign(spec)
    if redesign_reason:
        inspected = inspect_available_files_for_redesign(spec, output_path, redesign_reason)
        if inspected:
            return inspected
        return redesign_result(proposal, output_path, redesign_reason, spec)

    try:
        runner_type = str(spec.get("runner_type", "universal_tabular_csv")).lower()
        if runner_type == "universal_data_file":
            return run_universal_data_file_experiment(spec, output_path)
        if runner_type == "financial_sentiment_timeseries":
            return run_financial_sentiment_timeseries_experiment(spec, output_path)

        rows, data_paths = load_csvs(spec, output_path)
        target_column = str(spec["target_column"]).strip()
        if target_column.upper() in {"", "TO_VERIFY", "AUTO_TARGET"}:
            target_column = infer_target_column(rows)
        if target_column not in rows[0]:
            raise ValueError(f"Target column '{target_column}' does not exist in the CSV header.")

        task_type = infer_task_type(rows, target_column, str(spec["task_type"]))
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
            dataset_url=", ".join(dataset_urls_from_spec(spec)),
            runner_type=str(spec.get("runner_type", "universal_tabular_csv")),
            task_type=task_type,
            target_column=target_column,
            baseline=str(spec.get("baseline", "")),
            metrics=metrics,
            results=results,
            limitations=[
                "The universal_tabular_csv runner supports direct/local CSV classification/regression baselines only.",
                "More advanced models require a dedicated safe runner.",
            ],
            output_files=[*(str(path) for path in data_paths), str(output_path / "experiment_result.json"), str(output_path / "experiment_output.md")],
        )
        return write_outputs(output_path, result)
    except Exception as exc:
        return redesign_result(proposal, output_path, str(exc), spec)


if __name__ == "__main__":
    proposal_path = input("Enter proposal path or paste proposal text: ")
    print(run_experiment_stage(proposal_path))
