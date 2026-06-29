from __future__ import annotations

import os

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
    from backend.repo_library import REPO_LIBRARY, RepoMetadata, get_repo_by_id, select_repo_for_prompt
except ImportError:
    from pipeline_state import get_experiment_anchor
    from repo_library import REPO_LIBRARY, RepoMetadata, get_repo_by_id, select_repo_for_prompt


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


def parse_training_output(stdout: str) -> dict:
    epochs = []
    # Format: "Epoch 1: loss=0.1234, acc=0.9123, val_acc=0.9456"
    test_pattern = re.compile(
        r"Epoch (\d+): loss=([\d.]+), acc=([\d.]+), val_acc=([\d.]+)"
    )
    for match in test_pattern.finditer(stdout):
        epochs.append({
            "epoch": int(match.group(1)),
            "loss": float(match.group(2)),
            "train_acc": float(match.group(3)),
            "val_acc": float(match.group(4)),
            "accuracy_pct": float(match.group(4)) * 100,
        })

    final_accuracy = epochs[-1]["accuracy_pct"] if epochs else None
    success = final_accuracy is not None and final_accuracy >= 99.0

    return {
        "epochs_captured": len(epochs),
        "per_epoch_results": epochs,
        "final_accuracy_pct": final_accuracy,
        "success": success,
        "target": ">=99%",
    }


def dependency_imports(venv_python: Path, package: str) -> bool:
    returncode, stdout, stderr = run_command(
        [str(venv_python), "-c", f"import {package}"],
        cwd=Path("."),
        timeout=60,
    )
    return returncode == 0


def ensure_required_dependencies(venv_python: Path, venv_pip: Path) -> tuple[bool, str]:
    required_packages = ["torch", "torchvision"]
    return ensure_dependencies(venv_python, venv_pip, required_packages)


def import_name_for_dependency(package: str) -> str | None:
    aliases = {
        "scikit-learn": "sklearn",
    }
    if package == "python":
        return None
    return aliases.get(package, package.replace("-", "_"))


def ensure_dependencies(venv_python: Path, venv_pip: Path, packages: list[str]) -> tuple[bool, str]:
    missing_packages = []

    for package in packages:
        import_name = import_name_for_dependency(package)
        if not import_name:
            continue
        if dependency_imports(venv_python, import_name):
            print(f"[Experiment Agent] Dependency already installed: {package}")
        else:
            print(f"[Experiment Agent] Missing dependency: {package}")
            missing_packages.append(package)

    if not missing_packages:
        print("[Experiment Agent] All required dependencies are already installed.")
        return True, ""

    for package in missing_packages:
        print(f"[Experiment Agent] Installing missing dependency: {package}")
        returncode, stdout, stderr = run_command(
            [str(venv_pip), "install", package],
            cwd=Path("."),
            timeout=1800,
        )
        if returncode != 0:
            return False, stderr

    return True, ""


def repo_from_url(repo_url: str) -> RepoMetadata | None:
    for repo in REPO_LIBRARY:
        if repo.get("url") == repo_url:
            return repo
    return None


def select_repo_for_experiment(anchor: dict, proposal_text: str) -> RepoMetadata:
    match = re.search(r"^Repo:\s*(https://github\.com/\S+)", proposal_text, flags=re.MULTILINE)
    if match:
        repo = repo_from_url(match.group(1).rstrip(".,"))
        if repo:
            return repo

    repo = get_repo_by_id(anchor.get("repo_id", ""))
    if repo:
        return repo

    repo_url = anchor.get("repo_url", "")
    repo = repo_from_url(repo_url)
    if repo:
        return repo

    return select_repo_for_prompt(proposal_text or anchor.get("hypothesis", ""))


def find_runnable_entrypoint(repo: RepoMetadata, repo_path: Path) -> str | None:
    for entrypoint in repo.get("entrypoints", []):
        if not entrypoint.endswith(".py"):
            continue
        if (repo_path / entrypoint).exists():
            return entrypoint
    return None


def format_generic_experiment_report(
    repo: RepoMetadata,
    anchor: dict,
    returncode: int | None,
    stdout: str,
    stderr: str,
    elapsed_str: str,
    output_path: Path,
) -> str:
    status = "completed" if returncode == 0 else "not run automatically"
    if returncode not in {None, 0}:
        status = f"failed with exit code {returncode}"

    markdown = (
        "# Experiment Results\n\n"
        "## Outcome\n"
        f"Repository benchmark workflow {status}.\n\n"
        "## Selected Repository\n"
        f"- Repo: {repo['url']}\n"
        f"- Repo name: {repo['name']}\n"
        f"- Hypothesis: {anchor.get('hypothesis', '')}\n"
        f"- Metrics: {', '.join(repo.get('metrics', []))}\n"
        f"- Dependencies: {', '.join(repo.get('dependencies', []))}\n"
        f"- Runtime: {elapsed_str}\n\n"
        "## Notes\n"
        "The Experiment Agent now selects the repository from the pipeline repo library instead of using a hardcoded MNIST repository. "
        "If no runnable Python entrypoint is listed in the repo metadata, the agent clones the correct repository and records that an automated run strategy still needs to be added for this repo.\n\n"
        "## Stdout\n"
        f"```text\n{stdout[-5000:]}\n```\n\n"
        "## Stderr\n"
        f"```text\n{stderr[-5000:]}\n```\n"
    )
    (output_path / "experiment_output.md").write_text(markdown, encoding="utf-8")
    return markdown


def run_experiment_stage(
    proposal_input: str | Path,
    output_dir: str | Path = "paper_runs/latest/experiment",
) -> str:
    print("\n[Experiment Agent] Starting benchmark experiment...")
    anchor = get_experiment_anchor()
    proposal_text = read_text_or_path(proposal_input)
    selected_repo = select_repo_for_experiment(anchor, proposal_text)
    repo_url = selected_repo["url"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if CLONE_DIR.exists():
        print("[Experiment Agent] Removing previous clone...")
        shutil.rmtree(CLONE_DIR)

    print(f"[Experiment Agent] Cloning {selected_repo['name']}...")
    CLONE_DIR.parent.mkdir(parents=True, exist_ok=True)
    returncode, stdout, stderr = run_command(
        ["git", "clone", "--depth", "1", repo_url, str(CLONE_DIR)],
        cwd=Path("."),
        timeout=600,
    )
    if returncode != 0:
        return "# Experiment Failed\n\nFailed to clone repository.\n\nError: " + stderr

    repo_dir = CLONE_DIR
    if not repo_dir.exists():
        return "# Experiment Failed\n\nCould not find cloned repository directory."

    venv_python = VENV_DIR / "bin" / "python"
    venv_pip = VENV_DIR / "bin" / "pip"

    if venv_python.exists() and venv_pip.exists():
        print("[Experiment Agent] Reusing existing virtual environment.")
    else:
        print("[Experiment Agent] Creating virtual environment...")
        returncode, stdout, stderr = run_command(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            cwd=Path("."),
            timeout=60,
        )
        if returncode != 0:
            return "# Experiment Failed\n\nFailed to create virtual environment.\n\nError: " + stderr

    dependencies_ok, dependency_error = ensure_dependencies(
        venv_python,
        venv_pip,
        selected_repo.get("dependencies", []),
    )
    if not dependencies_ok:
        return "# Experiment Failed\n\nFailed to install dependencies.\n\nError: " + dependency_error

    entrypoint = find_runnable_entrypoint(selected_repo, repo_dir)
    if not entrypoint:
        return format_generic_experiment_report(
            selected_repo,
            anchor,
            None,
            "",
            "No automatic Python entrypoint is configured for this selected repository. Add a concrete .py entrypoint or repo-specific run strategy to repo_library.py.",
            "0m 0s",
            output_path,
        )

    if selected_repo["id"] != "mnist_cnn_pytorch":
        print(f"[Experiment Agent] Running selected repo entrypoint: {entrypoint}")
        start_time = time.time()
        returncode, stdout, stderr = run_command(
            [str(venv_python), entrypoint],
            cwd=repo_dir,
            timeout=1800,
        )
        elapsed = time.time() - start_time
        elapsed_str = str(int(elapsed // 60)) + "m " + str(int(elapsed % 60)) + "s"
        (output_path / "training_stdout.txt").write_text(stdout, encoding="utf-8")
        (output_path / "training_stderr.txt").write_text(stderr, encoding="utf-8")
        return format_generic_experiment_report(
            selected_repo,
            anchor,
            returncode,
            stdout,
            stderr,
            elapsed_str,
            output_path,
        )

    print("[Experiment Agent] Running training - this may take 15-20 minutes on CPU...")
    start_time = time.time()
    returncode, stdout, stderr = run_command(
        [str(venv_python), "train.py"],
        cwd=repo_dir,
        timeout=1800,
    )
    elapsed = time.time() - start_time
    elapsed_str = str(int(elapsed // 60)) + "m " + str(int(elapsed % 60)) + "s"

    (output_path / "training_stdout.txt").write_text(stdout, encoding="utf-8")
    (output_path / "training_stderr.txt").write_text(stderr, encoding="utf-8")

    if returncode != 0:
        return "# Experiment Failed\n\nTraining script exited with error code " + str(returncode) + "\n\nError: " + stderr[-2000:]

    results = parse_training_output(stdout)

    epoch_table = ""
    for i, epoch in enumerate(results["per_epoch_results"], 1):
        epoch_table += "| " + str(epoch["epoch"]) + " | " + str(round(epoch["loss"], 4)) + " | " + str(round(epoch["train_acc"], 4)) + " | " + str(round(epoch["val_acc"], 4)) + " |\n"

    if results["success"]:
        success_str = "SUCCESS - >=99% accuracy achieved"
    else:
        success_str = "FAILED - Did not reach 99% accuracy"

    hypothesis = anchor["hypothesis"]
    final_acc = str(results["final_accuracy_pct"])
    target = results["target"]
    epochs_captured = str(results["epochs_captured"])
    raw_log = stdout[-5000:]

    markdown = (
        "# Experiment Results\n\n"
        "## Outcome\n"
        + success_str + "\n\n"
        "## Key Results\n"
        "- Final Test Accuracy: " + final_acc + "%\n"
        "- Target: " + target + "\n"
        "- Training Time: " + elapsed_str + "\n"
        "- Epochs Completed: " + epochs_captured + "\n\n"
        "## Per-Epoch Results\n"
        "| Epoch | Loss | Train Acc | Val Acc |\n"
        "|-------|------|-----------|----------|\n"
        + epoch_table + "\n"
        "## Experiment Configuration\n"
        "- Repo: " + repo_url + "\n"
        "- Hypothesis: " + hypothesis + "\n"
        "- Architecture: SimpleCNN (see models.py)\n"
        "- Optimizer: Adam (lr=1e-3)\n"
        "- Batch Size: 128\n"
        "- Epochs: 10\n\n"
        "## Raw Training Log\n"
        + raw_log + "\n"
    )

    (output_path / "experiment_output.md").write_text(markdown, encoding="utf-8")
    print("[Experiment Agent] Done. Final accuracy: " + final_acc + "%")
    return markdown


if __name__ == "__main__":
    proposal_path = input("Enter proposal path or paste proposal text: ")
    print(run_experiment_stage(proposal_path))
