from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
    from backend.agent_api import call_agent_api
except ImportError:
    from pipeline_state import get_experiment_anchor
    from agent_api import call_agent_api

CLONE_DIR = Path("paper_runs/latest/experiment/repo")
VENV_DIR = Path("paper_runs/latest/experiment/venv").resolve()


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


def extract_setup_from_proposal(proposal_text: str) -> dict:
    try:
        json_str = proposal_text.split("EXPERIMENT SETUP JSON:")[1]
        brace_start = json_str.index("{")
        brace_end = json_str.rindex("}") + 1
        return json.loads(json_str[brace_start:brace_end])
    except Exception as e:
        print(f"[Experiment Agent] Could not extract setup JSON: {e}")
        return {"install_commands": [], "run_script": "", "data_setup_commands": [], "expected_metric": "benchmark performance"}

def install_packages(venv_pip: Path, packages: list[str]) -> None:
    for package in packages:
        package = package.strip()
        if not package:
            continue
        print(f"[Experiment Agent] Installing: {package}")
        returncode, _, stderr = run_command([str(venv_pip), "install", package], cwd=Path("."), timeout=300)
        if returncode != 0:
            base_package = package.split("==")[0].split(">=")[0].split("<=")[0].strip()
            if base_package != package:
                print(f"[Experiment Agent] Retrying without version pin: {base_package}")
                returncode, _, stderr = run_command([str(venv_pip), "install", base_package], cwd=Path("."), timeout=300)
            if returncode != 0:
                print(f"[Experiment Agent] Warning: could not install {package}: {stderr[:200]}")


def run_script_file(venv_python: Path, script: str, cwd: Path, timeout: int = 1800) -> tuple[int, str, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script)
        tmp_path = f.name
    try:
        return run_command([str(venv_python), tmp_path], cwd=cwd, timeout=timeout)
    finally:
        os.unlink(tmp_path)


def parse_results_with_llm(stdout: str, stderr: str, repo_url: str, expected_metric: str) -> str:
    return call_agent_api(
        f"You are a research engineer. Parse the following experiment output from {repo_url} "
        f"and summarize the results in markdown. "
        f"Look specifically for the metric: {expected_metric}. "
        f"Include: key metrics found, whether the run succeeded, and any errors if it failed. "
        f"Do not explain what you are about to do. Begin immediately with the summary.\n\n"
        f"STDOUT:\n{stdout[-3000:]}\n\n"
        f"STDERR:\n{stderr[-1000:]}",
        label="ResultsParser",
    )


def run_experiment_stage(
    proposal_input: str | Path,
    output_dir: str | Path = "paper_runs/latest/experiment",
) -> str:
    print("\n[Experiment Agent] Starting experiment...")
    anchor = get_experiment_anchor()
    proposal_text = read_text_or_path(proposal_input)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    repo_url = anchor["repo_url"]
    hypothesis = anchor["hypothesis"]

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
    install_commands = setup.get("install_commands", [])
    run_script_str = setup.get("run_script", "").strip()
    data_setup_commands = setup.get("data_setup_commands", [])
    expected_metric = setup.get("expected_metric", "benchmark performance")

    # Install packages
    install_packages(venv_pip, install_commands)

    # Install repo itself if it has setup.py or pyproject.toml
    if (CLONE_DIR / "setup.py").exists() or (CLONE_DIR / "pyproject.toml").exists():
        print("[Experiment Agent] Installing repo package...")
        run_command([str(venv_pip), "install", "-e", "."], cwd=CLONE_DIR, timeout=300)

    # Data setup
    for cmd in data_setup_commands:
        cmd = cmd.strip()
        if not cmd:
            continue
        print(f"[Experiment Agent] Data setup: {cmd}")
        returncode, _, stderr = run_command(cmd.split(), cwd=CLONE_DIR, timeout=600)
        if returncode != 0:
            print(f"[Experiment Agent] Data setup warning: {stderr[:200]}")

    # Run experiment
    if not run_script_str:
        return "# Experiment Failed\n\nCould not determine run script from proposal."

    print("[Experiment Agent] Running experiment script...")
    start_time = time.time()
    returncode, stdout, stderr = run_script_file(venv_python, run_script_str, cwd=CLONE_DIR)
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
        f"- Runtime: {elapsed_str}\n"
        f"- Exit code: {returncode}\n\n"
        "## Results\n"
        f"{results_summary}\n"
    )

    (output_path / "experiment_output.md").write_text(markdown, encoding="utf-8")
    print("[Experiment Agent] Done.")
    return markdown


if __name__ == "__main__":
    proposal_path = input("Enter proposal path or paste proposal text: ")
    print(run_experiment_stage(proposal_path))