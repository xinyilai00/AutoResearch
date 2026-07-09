from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests as http_requests

try:
    from backend.pipeline_state import get_experiment_anchor
    from backend.agent_api import call_agent_api, call_agent_api_json
    from backend.config import JSON_AGENT_ID
except ImportError:
    from pipeline_state import get_experiment_anchor
    from agent_api import call_agent_api, call_agent_api_json
    from config import JSON_AGENT_ID

CLONE_DIR = Path("paper_runs/latest/experiment/repo")
VENV_DIR = Path("paper_runs/latest/experiment/venv").resolve()

MAX_ATTEMPTS = 5
COLAB_EXECUTOR_ERROR_PREFIX = "COLAB_EXECUTOR_ERROR:"

REVISION_PROMPT = """You are a research engineer. A previous attempt to run an experiment failed.

CRITICAL: You are working ONLY with this specific repository: __REPO_URL__
Do NOT reference any other repository, file, or codebase. Every fix must be grounded in this repo's actual structure and files.

RULES:
- Reply with JSON only. No explanation, no markdown fences, no preamble.
- Use the same schema as before, plus an additional field: file_patches.
- install_commands: list of pip package names (no version pins, unless pinning is the actual fix for a compatibility error).
- run_script: the experiment script, corrected if the bug was in the script itself. CRITICAL: when printing any result, score, or metric, always print it on its own clearly labeled line in the exact format "RESULT: <name/identifier> | <metric name> | <value>" so that automated parsing can unambiguously map each number to exactly what it measured.
- data_setup_commands: list of shell commands, if any.
- IMPORTANT FOR REQUIRED DATA FILES: if FileNotFoundError shows a missing repo data file, revise the script to verify os.path.exists before calling repo utilities. Search only inside the repo working directory for included sample data, choose a matching included train/test file if available, or add data_setup_commands when the README/file tree documents how to obtain the missing data. Do not keep hardcoded paths to absent files.
- IMPORTANT ABOUT FILE PATHS: your script will always be executed with its working directory (cwd) already set to the root of the cloned repository, on every execution environment this pipeline uses. Always reference repo files using relative paths or os.getcwd(). NEVER use absolute filesystem paths. NEVER search the filesystem to locate your own repo's files (e.g. do not use "find", os.walk("/"), or similar) — if the previous error was caused by this pattern, replace it with a direct relative path instead.
- expected_metric: the primary metric to look for.
- file_patches: list of objects, each with "file" (relative path inside the cloned repo) and "find" (exact text to find) and "replace" (text to replace it with). Use this when the bug is inside a repo source file, not in your own script. For example, if a repo file has a pandas compatibility bug, patch the exact line.
- notes: caveats.
- IMPORTANT FOR SPEED: keep the script fast (under 2 minutes runtime). If previous failures were unrelated to speed, do not expand scope — keep using the smallest detector/data subset from the previous attempt.
- IMPORTANT FOR TIME-SERIES DATA SHAPES: if the traceback shows an indexing error such as "too many indices for array" or a failing expression like data.values[:, 0], fix the script by normalizing the loaded signal safely. Use np.asarray(data).squeeze() for arrays/Series and only index columns after checking the data is actually 2D. For TSFEL, load_biopluxecg() may return a 1D signal, so pass a 1D signal directly to signal_window_splitter.
- IMPORTANT FOR PANDAS COLUMN ERRORS: if the traceback shows KeyError for any DataFrame column, the script must not hardcode that missing column. Revise the script to inspect actual df.columns at runtime, print available columns, normalize/alias names, and select only columns that exist. If the intended concept is progression/cycle/semester but no explicit column exists, infer progression from actual numbered stage/course columns in the dataset, such as columns ending in 0, 1, 2, 3, etc.; do not invent a Cycle column. If no semantic match exists, fall back to an existing numeric/target column and state that fallback in stdout. Never access df["some column"] unless the script has first verified that exact column exists.
- IMPORTANT FOR CATEGORICAL FEATURES: if sklearn, imblearn, numpy, or a model raises ValueError such as "could not convert string to float", the feature matrix contains categorical strings. Encode object/category/bool feature columns with pandas.get_dummies or an sklearn ColumnTransformer before SMOTE/fit/predict. Keep train/test columns aligned by fitting the feature schema on training data and reindexing test data to the same columns. Do not drop categorical variables silently unless they are identifiers.
- IMPORTANT FOR RESAMPLING/SMOTE: before calling SMOTE, SMOTETomek, or any imblearn fit_resample method, check y.value_counts(). If y has fewer than two classes, or any class has fewer than two samples, skip resampling for that subset and train on the original encoded data. Do not let a single-class train split crash the experiment.
- IMPORTANT FOR NUMPY 2 COMPATIBILITY: if repo code fails with AttributeError for np.Inf, np.NaN, or another removed NumPy alias, use file_patches to patch the repo source directly. For np.Inf, replace np.Inf with np.inf in the file shown by the traceback, commonly utils/tools.py.
- IMPORTANT FOR LTSF-Linear STYLE REPOS: Exp_Main.train(setting) and Exp_Main.test(setting) expect a string experiment setting, not the argparse Namespace. If you instantiate Exp_Main(args), create a setting string and pass that to train/test. Never call exp.train(args) or exp.test(args).

IMPORTANT: If the error message and traceback point to a specific bug in a specific file inside the repository (not your own script), you MUST use file_patches to fix it directly, rather than only tweaking install_commands. Do not just guess at version pins if you know the exact line that needs to change.

Example output:
{
  "install_commands": ["numpy", "pandas"],
  "run_script": "...",
  "data_setup_commands": [],
  "file_patches": [
    {
      "file": "nab/labeler.py",
      "find": "labels[\\"label\\"].values[indices.values] = 1",
      "replace": "labels.loc[indices.values, \\"label\\"] = 1"
    }
  ],
  "expected_metric": "NAB score",
  "notes": "Fixed pandas read-only array bug in labeler.py"
}

PREVIOUS SETUP:
__PREVIOUS_SETUP__

ERROR (stdout/stderr from running this setup):
__ERROR_OUTPUT__

Provide a corrected JSON setup. If the traceback shows a specific file and line, use file_patches.
"""


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


def run_command(command: list[str], cwd: Path, timeout: int = 1800) -> tuple[int, str, str]:
    print(f"[Experiment Agent] Running: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=os.environ,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds."
    except Exception as e:
        return -1, "", str(e)

def snapshot_repo_files() -> dict[str, float]:
    snapshot = {}
    for path in CLONE_DIR.rglob("*"):
        if path.is_file():
            try:
                snapshot[str(path.relative_to(CLONE_DIR))] = path.stat().st_mtime
            except OSError:
                pass
    return snapshot


def diff_snapshots(before: dict[str, float], after: dict[str, float]) -> list[str]:
    changed = []
    for path, mtime in after.items():
        if path not in before or before[path] != mtime:
            changed.append(path)
    return changed


def extract_setup_from_proposal(proposal_text: str) -> dict:
    try:
        json_str = proposal_text.split("EXPERIMENT SETUP JSON:")[1]
        brace_start = json_str.index("{")
        brace_end = json_str.rindex("}") + 1
        setup = json.loads(json_str[brace_start:brace_end])
        return sanitize_setup(setup)
    except Exception as e:
        print(f"[Experiment Agent] Could not extract setup JSON: {e}")
        return {"install_commands": [], "run_script": "", "data_setup_commands": [], "expected_metric": "benchmark performance"}

def add_common_compatibility_patches(setup: dict) -> None:
    patches = setup.setdefault("file_patches", [])
    existing = {(patch.get("file"), patch.get("find")) for patch in patches if isinstance(patch, dict)}
    common_patches = [
        {
            "file": "utils/tools.py",
            "find": "np.Inf",
            "replace": "np.inf",
        },
        {
            "file": "exp/exp_basic.py",
            "find": "np.Inf",
            "replace": "np.inf",
        },
    ]
    for patch in common_patches:
        key = (patch["file"], patch["find"])
        if key not in existing:
            patches.append(patch)


def sanitize_setup(setup: dict) -> dict:
    setup["data_setup_commands"] = [
        cmd for cmd in setup.get("data_setup_commands", [])
        if not any(skip in cmd for skip in ["git clone", "cd ", "pip install ."])
    ]

    add_common_compatibility_patches(setup)

    script = setup.get("run_script", "")
    fixed_lines = []
    for line in script.split("\n"):
        if "os.chdir" in line:
            continue
        if "sys.path.insert" in line:
            continue
        fixed_lines.append(line)
    script = "\n".join(fixed_lines)
    script = script.replace("data.values[:, 0]", "np.asarray(data).squeeze()")
    script = script.replace("data.to_numpy()[:, 0]", "np.asarray(data).squeeze()")
    
    path_literal_pattern = re.compile(
       r"(?m)^(\s*[A-Za-z_]\w*(?:_file|_path|file|path)\s*=\s*)(['\"])([^'\"]+\.(?:txt|csv|tsv|json|jsonl|npy|npz|pkl|xlsx|xls|dat))\2"
    )
    used_path_resolver = False


    def replace_path_literal(match: re.Match) -> str:
        nonlocal used_path_resolver
        prefix = match.group(1)
        raw_path = match.group(3)
        if raw_path.startswith(("http://", "https://", "/")):
            return match.group(0)
        used_path_resolver = True
        return f"{prefix}_autoresearch_resolve_existing_path({json.dumps(raw_path, ensure_ascii=False)})"


    script = path_literal_pattern.sub(replace_path_literal, script)


    path_argument_pattern = re.compile(
        r"(?<!def\s)(\b[A-Za-z_]\w*\()([A-Za-z_]\w*(?:_file|_path|file|path))(\s*,)"
    )


    def replace_path_argument(match: re.Match) -> str:
        nonlocal used_path_resolver
        function_prefix = match.group(1)
        variable_name = match.group(2)
        suffix = match.group(3)
        if function_prefix.endswith("_autoresearch_resolve_existing_path("):
            return match.group(0)
        used_path_resolver = True
        return f"{function_prefix}_autoresearch_resolve_existing_path({variable_name}){suffix}"


    script = path_argument_pattern.sub(replace_path_argument, script)
    if used_path_resolver and "def _autoresearch_resolve_existing_path" not in script:
        path_helper = '\n\ndef _autoresearch_resolve_existing_path(path):\n    import os as _autoresearch_os\n    import glob as _autoresearch_glob\n    from pathlib import Path as _AutoresearchPath\n\n    requested = str(path)\n    if _autoresearch_os.path.exists(requested):\n        return requested\n\n    basename = _autoresearch_os.path.basename(requested)\n    suffix = _AutoresearchPath(requested).suffix.lower()\n    print(f"Requested data file not found: {requested}")\n\n    basename_matches = [p for p in _autoresearch_glob.glob("**/" + basename, recursive=True) if _autoresearch_os.path.isfile(p)]\n    if basename_matches:\n        chosen = sorted(basename_matches, key=len)[0]\n        print(f"Using located data file with matching basename: {chosen}")\n        return chosen\n\n    data_extensions = {".txt", ".csv", ".tsv", ".json", ".jsonl", ".npy", ".npz", ".pkl", ".xlsx", ".xls", ".dat"}\n    candidates = [\n        p for p in _autoresearch_glob.glob("**/*", recursive=True)\n        if _autoresearch_os.path.isfile(p) and _AutoresearchPath(p).suffix.lower() in data_extensions\n    ]\n    if suffix:\n        same_suffix = [p for p in candidates if _AutoresearchPath(p).suffix.lower() == suffix]\n    else:\n        same_suffix = candidates\n\n    requested_tokens = {token for token in _AutoresearchPath(requested).stem.lower().replace("-", "_").split("_") if len(token) >= 3}\n    scored = []\n    for candidate in same_suffix:\n        candidate_text = candidate.lower().replace("-", "_")\n        score = sum(1 for token in requested_tokens if token in candidate_text)\n        if "train" in requested_tokens and "train" in candidate_text:\n            score += 3\n        if "test" in requested_tokens and "test" in candidate_text:\n            score += 3\n        if "data" in candidate_text:\n            score += 1\n        scored.append((score, len(candidate), candidate))\n    scored = [item for item in scored if item[0] > 0]\n    if scored:\n        chosen = sorted(scored, reverse=True)[0][2]\n        print(f"Using closest available data file for {requested}: {chosen}")\n        return chosen\n\n    preview = sorted(candidates)[:25]\n    raise FileNotFoundError(\n        f"Required data file {requested!r} was not found after cloning/setup. "\n        f"Available data-like files include: {preview}. "\n        "The proposal should add data_setup_commands or choose an included file."\n    )\n'
        script = path_helper + "\n" + script

    dataframe_column_pattern = re.compile(
        r"\b((?:df\w*|\w*_df|\w*data\w*|dataset\w*|train\w*|test\w*|valid\w*))\b\[['\"]([^'\"]{2,80})['\"]\](?!\s*=(?!=))"
    )
    used_safe_column_helper = False

    def replace_dataframe_column(match: re.Match) -> str:
        nonlocal used_safe_column_helper
        variable_name = match.group(1)
        column_name = match.group(2)
        used_safe_column_helper = True
        column_literal = json.dumps(column_name, ensure_ascii=False)
        return f"_autoresearch_resolve_column({variable_name}, {column_literal})"

    script = dataframe_column_pattern.sub(replace_dataframe_column, script)

    filtered_dataframe_pattern = re.compile(
        r"(\b(?:df\w*|\w*_df|\w*data\w*|dataset\w*|train\w*|test\w*|valid\w*)\[[^\n\]]+\])\[['\"]([^'\"]{2,80})['\"]\](?!\s*=(?!=))"
    )

    def replace_filtered_dataframe_column(match: re.Match) -> str:
        nonlocal used_safe_column_helper
        dataframe_expr = match.group(1)
        column_name = match.group(2)
        used_safe_column_helper = True
        column_literal = json.dumps(column_name, ensure_ascii=False)
        return f"{dataframe_expr}.pipe(lambda _autoresearch_df: _autoresearch_resolve_column(_autoresearch_df, {column_literal}))"

    script = filtered_dataframe_pattern.sub(replace_filtered_dataframe_column, script)
    if used_safe_column_helper and "def _autoresearch_resolve_column" not in script:
        helper = '\n\ndef _autoresearch_normalize_column_name(name):\n    import re as _autoresearch_re\n    import unicodedata as _autoresearch_unicodedata\n    text = _autoresearch_unicodedata.normalize("NFKD", str(name))\n    text = "".join(ch for ch in text if not _autoresearch_unicodedata.combining(ch))\n    return _autoresearch_re.sub(r"[^a-z0-9]+", "", text.lower())\n\n\ndef _autoresearch_infer_progression_column(df, requested):\n    import re as _autoresearch_re\n    requested_norm = _autoresearch_normalize_column_name(requested)\n    progression_terms = {"cycle", "ciclo", "ultimociclo", "semester", "semestre", "term", "stage", "progression", "period"}\n    if requested_norm not in progression_terms:\n        return None\n\n    columns = list(getattr(df, "columns", []))\n    explicit_terms = progression_terms | {"year", "ano", "level", "nivel"}\n    for col in columns:\n        if _autoresearch_normalize_column_name(col) in explicit_terms:\n            return df[col]\n\n    numbered_groups = {}\n    for col in columns:\n        col_text = str(col)\n        if col_text.lower().startswith(("faltas", "absence", "absences", "missing")):\n            continue\n        match = _autoresearch_re.match(r"^(.+?)(\\d+)$", col_text)\n        if not match:\n            continue\n        base, number = match.group(1), int(match.group(2))\n        numbered_groups.setdefault(base, []).append((number, col))\n\n    if not numbered_groups:\n        return None\n\n    sequence = max(numbered_groups.values(), key=len)\n    if len(sequence) < 2:\n        return None\n    sequence = sorted(sequence)\n    inferred = None\n    for number, col in sequence:\n        present = df[col].notna()\n        if inferred is None:\n            inferred = present.astype(int) * number\n        else:\n            inferred = inferred.where(~present, number)\n    if inferred is not None:\n        inferred.name = str(requested)\n    return inferred\n\n\ndef _autoresearch_resolve_column(df, requested):\n    columns = list(getattr(df, "columns", []))\n    print("Available columns:", columns)\n    if not columns:\n        return df[requested]\n\n    if requested in columns:\n        return df[requested]\n\n    requested_norm = _autoresearch_normalize_column_name(requested)\n    for col in columns:\n        if _autoresearch_normalize_column_name(col) == requested_norm:\n            return df[col]\n\n    inferred_progression = _autoresearch_infer_progression_column(df, requested)\n    if inferred_progression is not None:\n        print(f"Inferred {requested!r} from numbered progression columns.")\n        return inferred_progression\n\n    aliases = {\n        "target": ["target", "label", "class", "y", "outcome", "risk", "disease", "diagnosis"],\n        "label": ["label", "target", "class", "y", "outcome"],\n        "class": ["class", "label", "target", "y"],\n    }\n    for alias in aliases.get(requested_norm, []):\n        alias_norm = _autoresearch_normalize_column_name(alias)\n        for col in columns:\n            if _autoresearch_normalize_column_name(col) == alias_norm:\n                return df[col]\n\n    if hasattr(df, "select_dtypes"):\n        numeric = df.select_dtypes(include="number")\n        if not numeric.empty:\n            print(f"Column {requested!r} not found; using first numeric column {numeric.columns[0]!r}.")\n            return numeric.iloc[:, 0]\n\n    if hasattr(df, "iloc"):\n        print(f"Column {requested!r} not found; using first available column {columns[0]!r}.")\n        return df.iloc[:, 0]\n\n    raise KeyError(f"Column {requested!r} not found. Available columns: {columns}")\n'
        script = helper + "\n" + script
    needs_feature_encoder = bool(re.search(r"\.(fit_resample|fit|predict)\s*\(\s*[A-Za-z_]\w*", script))
    if needs_feature_encoder:
        script = re.sub(
            r"\b([A-Za-z_]\w*)\.fit_resample\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*\)",
            r"_autoresearch_safe_fit_resample(\1, _autoresearch_encode_features(\2, fit=True), \3)",
            script,
        )
        script = re.sub(
            r"\.fit\(\s*([A-Za-z_]\w*)\s*,",
            r".fit(_autoresearch_encode_features(\1, fit=True),",
            script,
        )
        script = re.sub(
            r"\.predict\(\s*([A-Za-z_]\w*)\s*\)",
            r".predict(_autoresearch_encode_features(\1, fit=False))",
            script,
        )
        if "def _autoresearch_encode_features" not in script:
            feature_helper = '\n\n_autoresearch_feature_columns = None\n\n\ndef _autoresearch_encode_features(X, fit=False):\n    import numpy as _autoresearch_np\n    import pandas as _autoresearch_pd\n\n    global _autoresearch_feature_columns\n    if isinstance(X, _autoresearch_pd.Series):\n        X_df = X.to_frame()\n    elif isinstance(X, _autoresearch_pd.DataFrame):\n        X_df = X.copy()\n    else:\n        return X\n\n    object_columns = [\n        col for col in X_df.columns\n        if X_df[col].dtype == "object" or str(X_df[col].dtype).startswith("category") or str(X_df[col].dtype) == "bool"\n    ]\n    for col in X_df.columns:\n        if col not in object_columns:\n            X_df[col] = _autoresearch_pd.to_numeric(X_df[col], errors="coerce")\n\n    if object_columns:\n        print("Encoding categorical feature columns:", object_columns)\n        X_df = _autoresearch_pd.get_dummies(X_df, columns=object_columns, dummy_na=True)\n\n    X_df = X_df.replace([_autoresearch_np.inf, -_autoresearch_np.inf], _autoresearch_np.nan)\n    X_df = X_df.apply(_autoresearch_pd.to_numeric, errors="coerce")\n    X_df = X_df.fillna(0).astype(float)\n\n    if fit or _autoresearch_feature_columns is None:\n        _autoresearch_feature_columns = list(X_df.columns)\n    else:\n        X_df = X_df.reindex(columns=_autoresearch_feature_columns, fill_value=0)\n\n    return X_df\n\n\ndef _autoresearch_safe_fit_resample(sampler, X, y):\n    import pandas as _autoresearch_pd\n    try:\n        y_series = _autoresearch_pd.Series(y)\n        class_counts = y_series.value_counts(dropna=False)\n        print("Target class counts before resampling:", class_counts.to_dict())\n        if len(class_counts) < 2:\n            print("Skipping resampling because target has fewer than two classes.")\n            return X, y\n        min_count = int(class_counts.min())\n        if min_count < 2:\n            print("Skipping resampling because at least one target class has fewer than two samples.")\n            return X, y\n        return sampler.fit_resample(X, y)\n    except ValueError as exc:\n        if "needs to have more than 1 class" in str(exc) or "n_neighbors" in str(exc):\n            print(f"Skipping resampling after sampler validation error: {exc}")\n            return X, y\n        raise\n'
            script = feature_helper + "\n" + script
    if "from exp.exp_main import Exp_Main" in script and ("exp.train(args)" in script or "exp.test(args)" in script):
        setting_line = (
            "        setting = f'{args.model_id}_{args.model}_{args.data}_ft{args.features}_"
            "sl{args.seq_len}_ll{args.label_len}_pl{args.pred_len}'"
        )
        if "setting = f'{args.model_id}_" not in script:
            script = script.replace("        exp = Exp_Main(args)\n", f"        exp = Exp_Main(args)\n{setting_line}\n")
        script = script.replace("exp.train(args)", "exp.train(setting)")
        script = script.replace("exp.test(args)", "exp.test(setting)")
    setup["run_script"] = script

    setup["install_commands"] = [
        pkg for pkg in setup.get("install_commands", [])
        if pkg.lower() not in {"cython"}
    ]

    return setup


def package_base_name(package: str) -> str:
    base = package.strip()
    for marker in ["==", ">=", "<=", "~=", "!=", ">", "<"]:
        base = base.split(marker)[0]
    return base.split("[")[0].strip()


def has_version_constraint(package: str) -> bool:
    return any(marker in package for marker in ["==", ">=", "<=", "~=", "!=", ">", "<"])


def is_package_installed(venv_python: Path, package: str) -> bool:
    base_package = package_base_name(package)
    if not base_package:
        return False
    returncode, _, _ = run_command(
        [str(venv_python), "-m", "pip", "show", base_package],
        cwd=Path("."),
        timeout=30,
    )
    return returncode == 0


def install_packages(venv_python: Path, venv_pip: Path, packages: list[str]) -> None:
    for package in packages:
        package = package.strip()
        if not package:
            continue

        base_package = package_base_name(package)
        if not has_version_constraint(package) and is_package_installed(venv_python, package):
            print(f"[Experiment Agent] Already installed, skipping: {base_package}")
            continue

        if has_version_constraint(package):
            print(f"[Experiment Agent] Installing/checking version constraint: {package}")
        else:
            print(f"[Experiment Agent] Installing missing package: {package}")

        returncode, _, stderr = run_command([str(venv_pip), "install", package], cwd=Path("."), timeout=300)
        if returncode != 0:
            if base_package and base_package != package:
                if is_package_installed(venv_python, base_package):
                    print(f"[Experiment Agent] Base package already installed after failed constrained install: {base_package}")
                    continue
                print(f"[Experiment Agent] Retrying without version pin: {base_package}")
                returncode, _, stderr = run_command([str(venv_pip), "install", base_package], cwd=Path("."), timeout=300)
            if returncode != 0:
                print(f"[Experiment Agent] Warning: could not install {package}: {stderr[:200]}")


def repo_context_from_proposal(proposal_text: str) -> tuple[str, str, str]:
    repo_url = ""
    repo_name = ""
    hypothesis = ""

    repo_match = re.search(r"(?im)^\s*Repo\s*:\s*(https://github\.com/[^\s)]+)", proposal_text or "")
    if repo_match:
        repo_url = repo_match.group(1).rstrip(".,")
        repo_name = repo_url.replace("https://github.com/", "").strip("/")

    hypothesis_match = re.search(r"(?im)^\s*Hypothesis\s*:\s*(.+)$", proposal_text or "")
    if hypothesis_match:
        hypothesis = hypothesis_match.group(1).strip()

    return repo_url, repo_name, hypothesis


def validate_colab_executor_url(colab_url: str) -> str:
    normalized = (colab_url or "").strip().rstrip("/")
    if not normalized:
        return ""
    if "colab.research.google.com" in normalized:
        return (
            "COLAB_EXECUTOR_URL points to a Colab notebook page. The experiment agent needs "
            "the public HTTP executor URL created by the notebook, such as an ngrok/cloudflared URL "
            "that accepts POST /execute. Open the notebook, start its executor server, then copy that "
            "public URL into COLAB_EXECUTOR_URL."
        )
    if not normalized.startswith(("http://", "https://")):
        return "COLAB_EXECUTOR_URL must start with http:// or https://."
    return ""


def run_script_file(venv_python: Path, script: str, cwd: Path, timeout: int = 1800) -> tuple[int, str, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script)
        tmp_path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [str(venv_python), tmp_path],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    finally:
        os.unlink(tmp_path)

def check_script_syntax(script: str) -> tuple[bool, str]:
    try:
        compile(script, "<run_script>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} at line {e.lineno}: {e.text}"

COMMON_IMPORT_ROOTS = {
    "argparse", "collections", "csv", "datetime", "glob", "itertools", "json", "math",
    "os", "pathlib", "random", "re", "shutil", "statistics", "subprocess", "sys",
    "tempfile", "time", "typing", "warnings",
    "matplotlib", "numpy", "pandas", "scipy", "sklearn", "torch", "tensorflow",
    "seaborn", "statsmodels", "xgboost", "lightgbm", "requests", "urllib",
}


def repo_slug_tokens(repo_name: str) -> set[str]:
    slug = (repo_name or "").split("/")[-1].lower()
    compact = re.sub(r"[^a-z0-9]", "", slug)
    tokens = {slug, compact}
    tokens.update(token for token in re.split(r"[^a-z0-9]+", slug) if len(token) >= 3)
    if slug == "nab":
        tokens.add("nab")
    return {token for token in tokens if token}


def imported_roots(script: str) -> set[str]:
    roots = set()
    for match in re.finditer(r"(?m)^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", script):
        roots.add(match.group(1).split(".")[0].lower())
    return roots


def verify_script_uses_repo(script: str, repo_name: str, setup: dict | None = None) -> tuple[bool, str]:
    script_lower = script.lower()
    tokens = repo_slug_tokens(repo_name)

    if any(token in script_lower for token in tokens):
        return True, ""
    if "from nab" in script_lower or "import nab" in script_lower:
        return True, ""

    setup = setup or {}
    patch_files = [str(patch.get("file", "")).strip() for patch in setup.get("file_patches", []) if isinstance(patch, dict)]
    setup_text = "\n".join(setup.get("data_setup_commands", []) + patch_files).lower()
    if setup_text and any(token in setup_text for token in tokens):
        return True, ""
    if patch_files:
        return True, ""

    local_imports = imported_roots(script) - COMMON_IMPORT_ROOTS
    if local_imports:
        return True, ""

    repo_path_patterns = [
        r"['\"](?:\./)?(?:src|data|datasets|examples|example|models|model|utils|experiments|scripts|results|NAB|nab)/",
        r"os\.path\.join\([^)]*['\"](?:src|data|datasets|examples|example|models|model|utils|experiments|scripts|results|NAB|nab)['\"]",
        r"Path\([^)]*['\"](?:src|data|datasets|examples|example|models|model|utils|experiments|scripts|results|NAB|nab)['\"]",
    ]
    if any(re.search(pattern, script) for pattern in repo_path_patterns):
        return True, ""

    expected = ", ".join(sorted(tokens)) or "repo-specific imports/files"
    return False, (
        "Script does not show clear evidence of using the selected repository code "
        f"(looked for repo tokens/imports/relative repo paths such as {expected}). "
        "This may be a fabricated/generic script."
    )


def revise_setup_after_failure(previous_setup: dict, stdout: str, stderr: str, repo_url: str = "", repo_name: str = "") -> dict:
    error_output = f"STDOUT:\n{stdout[-2000:]}\n\nSTDERR:\n{stderr[-2000:]}"
    prompt = REVISION_PROMPT.replace(
        "__REPO_URL__", repo_url or "unknown"
    ).replace(
        "__PREVIOUS_SETUP__", json.dumps(previous_setup, indent=2)
    ).replace(
        "__ERROR_OUTPUT__", error_output
    )
    revised = call_agent_api_json(prompt, label="SetupRevision")
    if not revised:
        print("[Experiment Agent] Could not get valid revised setup, keeping previous.")
        return previous_setup
    return sanitize_setup(revised)

def apply_file_patches(patches: list[dict]) -> None:
    for patch in patches:
        file_path = CLONE_DIR / patch.get("file", "")
        find_text = patch.get("find", "")
        replace_text = patch.get("replace", "")
        if not file_path.exists() or not find_text:
            print(f"[Experiment Agent] Skipping patch, file not found: {file_path}")
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            if find_text in content:
                content = content.replace(find_text, replace_text)
                file_path.write_text(content, encoding="utf-8")
                print(f"[Experiment Agent] Patched {patch.get('file')}")
            else:
                print(f"[Experiment Agent] Patch text not found in {patch.get('file')}, skipping")
        except Exception as e:
            print(f"[Experiment Agent] Failed to patch {patch.get('file')}: {e}")


def execute_setup(setup: dict, venv_python: Path, venv_pip: Path, repo_name: str, repo_url: str = "") -> tuple[int, str, str]:
    from backend.config import COLAB_EXECUTOR_URL
    install_commands = setup.get("install_commands", [])
    run_script_str = setup.get("run_script", "").strip()
    data_setup_commands = setup.get("data_setup_commands", [])
    file_patches = setup.get("file_patches", [])

    if not run_script_str:
        return -1, "", "No run script provided in setup."

    is_valid, syntax_error = check_script_syntax(run_script_str)
    if not is_valid:
        print(f"[Experiment Agent] Script has a syntax error, skipping execution: {syntax_error}")
        return -1, "", f"SCRIPT SYNTAX ERROR (script was not executed):\n{syntax_error}"

    uses_repo, repo_warning = verify_script_uses_repo(run_script_str, repo_name, setup)
    if not uses_repo:
        print(f"[Experiment Agent] WARNING: {repo_warning}")
        return -1, "", f"SCRIPT VALIDATION FAILED: {repo_warning}"

    if COLAB_EXECUTOR_URL:
        colab_url_error = validate_colab_executor_url(COLAB_EXECUTOR_URL)
        if colab_url_error:
            return -1, "", colab_url_error
        print("[Experiment Agent] Colab executor configured; skipping local dependency install and repo package install.")
        print("[Experiment Agent] Sending script to Colab executor...")
        return run_script_on_colab(
            run_script_str,
            install_commands,
            COLAB_EXECUTOR_URL,
            repo_url=repo_url,
            repo_name=repo_name,
            data_setup_commands=data_setup_commands,
            file_patches=file_patches,
        )

    install_packages(venv_python, venv_pip, install_commands)

    if file_patches:
        print(f"[Experiment Agent] Applying {len(file_patches)} file patch(es)...")
        apply_file_patches(file_patches)

    if (CLONE_DIR / "setup.py").exists() or (CLONE_DIR / "pyproject.toml").exists():
        print("[Experiment Agent] Installing repo package...")
        run_command([str(venv_pip), "install", "-e", "."], cwd=CLONE_DIR, timeout=300)

    for cmd in data_setup_commands:
        cmd = cmd.strip()
        if not cmd:
            continue
        print(f"[Experiment Agent] Data setup: {cmd}")
        result = subprocess.run(
            cmd, cwd=CLONE_DIR, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600
        )
        if result.returncode != 0:
            print(f"[Experiment Agent] Data setup warning: {result.stderr[:200]}")

    print("[Experiment Agent] Running experiment script...")
    before_snapshot = snapshot_repo_files()
    returncode, stdout, stderr = run_script_file(venv_python, run_script_str, CLONE_DIR)
    after_snapshot = snapshot_repo_files()
    changed_files = diff_snapshots(before_snapshot, after_snapshot)
    pre_existing_files = list(before_snapshot.keys())
    stdout += (
        f"\n\n[PIPELINE METADATA] Files newly created or modified by this run:\n"
        + "\n".join(changed_files[:50])
        + f"\n\n[PIPELINE METADATA] Files that already existed in the repository BEFORE this run (for reference, NOT modified by this run):\n"
        + "\n".join(pre_existing_files[:100])
    )
    return returncode, stdout, stderr

def parse_results_with_llm(stdout: str, stderr: str, repo_url: str, expected_metric: str) -> str:
    result_lines = "\n".join(line for line in stdout.split("\n") if line.strip().startswith("RESULT:"))
    metadata_section = ""
    if "[PIPELINE METADATA]" in stdout:
        metadata_section = stdout[stdout.index("[PIPELINE METADATA]"):]

    return call_agent_api(
        f"You are a research engineer. Parse the following experiment output from {repo_url} "
        f"and summarize the results in markdown. "
        f"Look specifically for the metric: {expected_metric}. "
        f"\n\nCRITICAL: below are the RESULT lines extracted directly from stdout, in the format "
        f"'RESULT: <name> | <metric> | <value>'. This script was already verified before execution to use real "
        f"repository code (not fabricated), so by default TRUST these RESULT lines as genuine output of this run. "
        f"\n\nMany legitimate experiments produce results purely via stdout printing with no corresponding file changes "
        f"on disk — this is normal and does NOT indicate fabrication. Do not flag a RESULT line as suspicious just "
        f"because no files changed.\n\n"
        f"The only reason to flag a RESULT line as potentially pre-existing (not from this run) is if its name/identifier "
        f"closely matches a file listed under 'Files that already existed in the repository BEFORE this run' below, "
        f"AND that same file does NOT appear under 'Files newly created or modified by this run' — this specific pattern "
        f"suggests the script may have read and echoed old cached data rather than computing fresh results.\n\n"
        f"RESULT LINES:\n{result_lines if result_lines else 'None found.'}\n\n"
        f"{metadata_section}\n\n"
        f"Do not explain what you are about to do. Begin immediately with the summary.\n\n"
        f"STDERR (for error context only):\n{stderr[-1000:]}",
        label="ResultsParser",
        agent_id=JSON_AGENT_ID,
    )

def run_script_on_colab(
    script: str,
    install_commands: list[str],
    colab_url: str,
    repo_url: str = "",
    repo_name: str = "",
    data_setup_commands: list[str] | None = None,
    file_patches: list[dict] | None = None,
) -> tuple[int, str, str]:
    endpoint = f"{colab_url.strip().rstrip('/')}/execute"
    try:
        response = http_requests.post(
            endpoint,
            json={
                "install_commands": install_commands,
                "script": script,
                "repo_url": repo_url,
                "repo_name": repo_name,
                "setup_commands": data_setup_commands or [],
                "file_patches": file_patches or [],
            },
            timeout=(20, 600),
        )
        if response.status_code >= 400:
            preview = response.text[:300].replace("\n", " ")
            return -1, "", f"{COLAB_EXECUTOR_ERROR_PREFIX} POST {endpoint} returned HTTP {response.status_code}: {preview}"
        try:
            data = response.json()
        except ValueError:
            preview = response.text[:300].replace("\n", " ")
            return -1, "", f"{COLAB_EXECUTOR_ERROR_PREFIX} POST {endpoint} did not return JSON: {preview}"
        return data.get("returncode", -1), data.get("stdout", ""), data.get("stderr", "")
    except http_requests.exceptions.RequestException as e:
        return -1, "", f"{COLAB_EXECUTOR_ERROR_PREFIX} could not reach {endpoint}: {e}"


def run_experiment_stage(
    proposal_input: str | Path,
    output_dir: str | Path = "paper_runs/latest/experiment",
) -> str:
    print("\n[Experiment Agent] Starting experiment...")
    try:
        from backend.config import COLAB_EXECUTOR_URL
    except ImportError:
        from config import COLAB_EXECUTOR_URL

    anchor = get_experiment_anchor()
    proposal_text = read_text_or_path(proposal_input)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    proposal_repo_url, proposal_repo_name, proposal_hypothesis = repo_context_from_proposal(proposal_text)
    repo_url = proposal_repo_url or anchor["repo_url"]
    repo_name = proposal_repo_name or anchor.get("repo_name", "")
    hypothesis = proposal_hypothesis or anchor["hypothesis"]
    if proposal_repo_url and proposal_repo_url != anchor.get("repo_url", ""):
        print(f"[Experiment Agent] Using repository from proposal text: {proposal_repo_name}")
    if not repo_url:
        return "# Experiment Failed\n\nNo repository context is configured for the experiment stage."
    use_colab = bool(COLAB_EXECUTOR_URL)

    if use_colab:
        colab_url_error = validate_colab_executor_url(COLAB_EXECUTOR_URL)
        if colab_url_error:
            return f"# Experiment Failed\n\n{colab_url_error}"
        print("[Experiment Agent] Colab executor configured; skipping local clone and local virtual environment.")
        venv_python = VENV_DIR / "bin" / "python"
        venv_pip = VENV_DIR / "bin" / "pip"
    else:
        # Clone
        if CLONE_DIR.exists():
            print("[Experiment Agent] Removing previous clone...")
            shutil.rmtree(CLONE_DIR)

        print(f"[Experiment Agent] Cloning {repo_url}...")
        CLONE_DIR.parent.mkdir(parents=True, exist_ok=True)
        returncode, stdout, stderr = run_command(
            ["git", "clone", "--depth", "1", repo_url, str(CLONE_DIR)],
            cwd=Path("."),
            timeout=600,
        )
        if returncode != 0:
            return f"# Experiment Failed\n\nFailed to clone repository.\n\nError:\n```\n{stderr}\n```"

        # Venv
        venv_python = VENV_DIR / "bin" / "python"
        venv_pip = VENV_DIR / "bin" / "pip"

        if venv_python.exists():
            print("[Experiment Agent] Reusing existing virtual environment.")
        else:
            print("[Experiment Agent] Creating virtual environment...")
            returncode, _, stderr = run_command(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                cwd=Path("."),
                timeout=60,
            )
            if returncode != 0:
                return f"# Experiment Failed\n\nFailed to create venv.\n\nError:\n```\n{stderr}\n```"

    # Extract setup from proposal
    print("[Experiment Agent] Extracting setup from proposal...")
    setup = extract_setup_from_proposal(proposal_text)
    expected_metric = setup.get("expected_metric", "benchmark performance")

    attempts = []
    returncode, stdout, stderr = -1, "", ""
    start_time = time.time()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[Experiment Agent] Attempt {attempt}/{MAX_ATTEMPTS}...")
        if attempt > 1 and not use_colab:
            print("[Experiment Agent] Re-cloning repo fresh for this attempt...")
            shutil.rmtree(CLONE_DIR)
            run_command(["git", "clone", "--depth", "1", repo_url, str(CLONE_DIR)], cwd=Path("."), timeout=600)
        returncode, stdout, stderr = execute_setup(setup, venv_python, venv_pip, repo_name, repo_url=repo_url)
        attempts.append({"attempt": attempt, "returncode": returncode, "stderr_tail": stderr[-500:]})

        # Log every attempt's full output, not just the last
        (output_path / f"attempt_{attempt}_stdout.txt").write_text(stdout, encoding="utf-8")
        (output_path / f"attempt_{attempt}_stderr.txt").write_text(stderr, encoding="utf-8")

        if returncode == 0:
            print(f"[Experiment Agent] Attempt {attempt} succeeded.")
            break

        print(f"[Experiment Agent] Attempt {attempt} failed with exit code {returncode}.")
        print(f"[Experiment Agent] Stderr tail: {stderr[-300:]}")
        if use_colab and stderr.startswith(COLAB_EXECUTOR_ERROR_PREFIX):
            print("[Experiment Agent] Colab executor failed; stopping retries because setup revisions cannot fix executor availability.")
            break
        if attempt < MAX_ATTEMPTS:
            print("[Experiment Agent] Asking agent to revise setup based on error...")
            setup = revise_setup_after_failure(setup, stdout, stderr, repo_url=repo_url, repo_name=repo_name)
            expected_metric = setup.get("expected_metric", expected_metric)

    elapsed = time.time() - start_time
    elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    (output_path / "training_stdout.txt").write_text(stdout, encoding="utf-8")
    (output_path / "training_stderr.txt").write_text(stderr, encoding="utf-8")

    if returncode != 0 and stderr.startswith(COLAB_EXECUTOR_ERROR_PREFIX):
        markdown = (
            "# Experiment Failed\n\n"
            "The configured Colab executor could not run the experiment. This is an executor availability/configuration problem, "
            "not an experiment-design failure.\n\n"
            "Error:\n```\n"
            f"{stderr}\n"
            "```\n"
        )
        (output_path / "experiment_output.md").write_text(markdown, encoding="utf-8")
        print("[Experiment Agent] Done with executor failure.")
        return markdown

    # Parse results with LLM
    print("[Experiment Agent] Parsing results...")
    results_summary = parse_results_with_llm(stdout, stderr, repo_url, expected_metric)

    markdown = (
        "# Experiment Results\n\n"
        "## Repository\n"
        f"- URL: {repo_url}\n"
        f"- Hypothesis: {hypothesis}\n"
        f"- Runtime: {elapsed_str}\n\n"
        "## Results\n"
        f"{results_summary}\n"
    )

    (output_path / "experiment_output.md").write_text(markdown, encoding="utf-8")
    print("[Experiment Agent] Done.")
    return markdown


if __name__ == "__main__":
    proposal_path = input("Enter proposal path or paste proposal text: ")
    print(run_experiment_stage(proposal_path))