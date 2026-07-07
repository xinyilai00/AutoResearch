from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from turtle import setup

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

REVISION_PROMPT = """You are a research engineer. A previous attempt to run an experiment failed.

CRITICAL: You are working ONLY with this specific repository: __REPO_URL__
Do NOT reference any other repository, file, or codebase. Every fix must be grounded in this repo's actual structure and files.

RULES:
- Reply with JSON only. No explanation, no markdown fences, no preamble.
- Use the same schema as before, plus an additional field: file_patches.
- install_commands: list of pip package names (no version pins, unless pinning is the actual fix for a compatibility error).
- run_script: the experiment script, corrected if the bug was in the script itself. CRITICAL: when printing any result, score, or metric, always print it on its own clearly labeled line in the exact format "RESULT: <name/identifier> | <metric name> | <value>" so that automated parsing can unambiguously map each number to exactly what it measured.
- data_setup_commands: list of shell commands, if any.
- IMPORTANT ABOUT FILE PATHS: your script will always be executed with its working directory (cwd) already set to the root of the cloned repository, on every execution environment this pipeline uses. Always reference repo files using relative paths or os.getcwd(). NEVER use absolute filesystem paths. NEVER search the filesystem to locate your own repo's files (e.g. do not use "find", os.walk("/"), or similar) — if the previous error was caused by this pattern, replace it with a direct relative path instead.
- expected_metric: the primary metric to look for.
- file_patches: list of objects, each with "file" (relative path inside the cloned repo) and "find" (exact text to find) and "replace" (text to replace it with). Use this when the bug is inside a repo source file, not in your own script. For example, if a repo file has a pandas compatibility bug, patch the exact line.
- notes: caveats.
- IMPORTANT FOR SPEED: keep the script fast (under 2 minutes runtime). If previous failures were unrelated to speed, do not expand scope — keep using the smallest detector/data subset from the previous attempt.

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

def sanitize_setup(setup: dict) -> dict:
    setup["data_setup_commands"] = [
        cmd for cmd in setup.get("data_setup_commands", [])
        if not any(skip in cmd for skip in ["git clone", "cd ", "pip install ."])
    ]

    script = setup.get("run_script", "")
    fixed_lines = []
    for line in script.split("\n"):
        if "os.chdir" in line:
            continue
        if "sys.path.insert" in line:
            continue
        fixed_lines.append(line)
    setup["run_script"] = "\n".join(fixed_lines)

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

def verify_script_uses_repo(script: str, repo_name: str) -> tuple[bool, str]:
    # Heuristic: the script should reference the actual repo's package name
    # e.g. for numenta/NAB, expect "nab." somewhere in imports
    package_hint = repo_name.split("/")[-1].lower()
    script_lower = script.lower()
    if package_hint in script_lower or "from nab" in script_lower or "import nab" in script_lower:
        return True, ""
    return False, f"Script does not appear to use the actual repository's code (expected references to '{package_hint}' or 'nab' package, found none). This may be a fabricated/generic script."


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

    uses_repo, repo_warning = verify_script_uses_repo(run_script_str, repo_name)
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
    try:
        response = http_requests.post(
            f"{colab_url.strip().rstrip('/')}/execute",
            json={
                "install_commands": install_commands,
                "script": script,
                "repo_url": repo_url,
                "repo_name": repo_name,
                "setup_commands": data_setup_commands or [],
                "file_patches": file_patches or [],
            },
            timeout=1800
        )
        data = response.json()
        return data["returncode"], data["stdout"], data["stderr"]
    except Exception as e:
        return -1, "", f"Colab executor error: {e}"


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

    repo_url = anchor["repo_url"]
    repo_name = anchor.get("repo_name", "")
    hypothesis = anchor["hypothesis"]
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
        if attempt < MAX_ATTEMPTS:
            print("[Experiment Agent] Asking agent to revise setup based on error...")
            setup = revise_setup_after_failure(setup, stdout, stderr, repo_url=repo_url, repo_name=repo_name)
            expected_metric = setup.get("expected_metric", expected_metric)

    elapsed = time.time() - start_time
    elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    (output_path / "training_stdout.txt").write_text(stdout, encoding="utf-8")
    (output_path / "training_stderr.txt").write_text(stderr, encoding="utf-8")

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