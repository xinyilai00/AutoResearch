from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
except ImportError:
    from pipeline_state import get_experiment_anchor


CLONE_DIR = Path("paper_runs/latest/experiment/repo")
VENV_DIR = Path("paper_runs/latest/experiment/venv")


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
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds."
    except Exception as e:
        return -1, "", str(e)


def parse_training_output(stdout: str) -> dict:
    epochs = []
    test_pattern = re.compile(
        r"Test set: Average loss: ([\d.]+), Accuracy: (\d+)/(\d+) \(([\d.]+)%\)"
    )
    for match in test_pattern.finditer(stdout):
        epochs.append({
            "loss": float(match.group(1)),
            "correct": int(match.group(2)),
            "total": int(match.group(3)),
            "accuracy_pct": float(match.group(4)),
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


def run_experiment_stage(
    proposal_input: str | Path,
    output_dir: str | Path = "paper_runs/latest/experiment",
) -> str:
    print("\n[Experiment Agent] Starting MNIST replication experiment...")
    anchor = get_experiment_anchor()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if CLONE_DIR.exists():
        print("[Experiment Agent] Removing previous clone...")
        shutil.rmtree(CLONE_DIR)
    if VENV_DIR.exists():
        print("[Experiment Agent] Removing previous venv...")
        shutil.rmtree(VENV_DIR)

    print("[Experiment Agent] Cloning pytorch/examples...")
    CLONE_DIR.parent.mkdir(parents=True, exist_ok=True)
    returncode, stdout, stderr = run_command(
        ["git", "clone", "--depth", "1", "https://github.com/pytorch/examples.git", str(CLONE_DIR)],
        cwd=Path("."),
        timeout=120,
    )
    if returncode != 0:
        return "# Experiment Failed\n\nFailed to clone repository.\n\nError: " + stderr

    mnist_dir = CLONE_DIR / "mnist"
    if not mnist_dir.exists():
        return "# Experiment Failed\n\nCould not find mnist/ directory in cloned repo."

    print("[Experiment Agent] Creating virtual environment...")
    returncode, stdout, stderr = run_command(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        cwd=Path("."),
        timeout=60,
    )
    if returncode != 0:
        return "# Experiment Failed\n\nFailed to create virtual environment.\n\nError: " + stderr

    venv_python = VENV_DIR / "bin" / "python"
    venv_pip = VENV_DIR / "bin" / "pip"

    print("[Experiment Agent] Installing dependencies...")
    returncode, stdout, stderr = run_command(
        [str(venv_pip), "install", "-r", "requirements.txt"],
        cwd=mnist_dir,
        timeout=600,
    )
    if returncode != 0:
        return "# Experiment Failed\n\nFailed to install dependencies.\n\nError: " + stderr

    print("[Experiment Agent] Running training - this may take 15-20 minutes on CPU...")
    start_time = time.time()
    returncode, stdout, stderr = run_command(
        [str(venv_python), "main.py"],
        cwd=mnist_dir,
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
        epoch_table += "| " + str(i) + " | " + str(round(epoch["loss"], 4)) + " | " + str(epoch["correct"]) + "/" + str(epoch["total"]) + " | " + str(epoch["accuracy_pct"]) + "% |\n"

    if results["success"]:
        success_str = "SUCCESS - >=99% accuracy achieved"
    else:
        success_str = "FAILED - Did not reach 99% accuracy"

    repo_url = anchor["repo_url"]
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
        "| Epoch | Test Loss | Correct | Accuracy |\n"
        "|-------|-----------|---------|----------|\n"
        + epoch_table + "\n"
        "## Experiment Configuration\n"
        "- Repo: " + repo_url + "\n"
        "- Hypothesis: " + hypothesis + "\n"
        "- Architecture: Two-layer CNN (Conv1: 1->32, Conv2: 32->64), Dropout(0.25, 0.50), FC(9216->128->10)\n"
        "- Optimizer: Adadelta (lr=1.0, gamma=0.7)\n"
        "- Batch Size: 64\n"
        "- Epochs: 14\n\n"
        "## Raw Training Log\n"
        + raw_log + "\n"
    )

    (output_path / "experiment_output.md").write_text(markdown, encoding="utf-8")
    print("[Experiment Agent] Done. Final accuracy: " + final_acc + "%")
    return markdown


if __name__ == "__main__":
    proposal_path = input("Enter proposal path or paste proposal text: ")
    print(run_experiment_stage(proposal_path))