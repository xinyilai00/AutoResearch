from __future__ import annotations

import json
import urllib.request
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
except ImportError:
    from pipeline_state import get_experiment_anchor


PYTORCH_MNIST_REPO_API = "https://api.github.com/repos/pytorch/examples/contents/mnist"
PYTORCH_MNIST_MAIN_PY = "https://raw.githubusercontent.com/pytorch/examples/main/mnist/main.py"
PYTORCH_MNIST_REQUIREMENTS = "https://raw.githubusercontent.com/pytorch/examples/main/mnist/requirements.txt"


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
    print("\n[Proposal Agent] Fetching pytorch/examples/mnist repo...")
    anchor = get_experiment_anchor()
    repo_url = anchor["repo_url"]
    hypothesis = anchor["hypothesis"]

    # Fetch the actual source files from the repo
    main_py = fetch_url(PYTORCH_MNIST_MAIN_PY)
    requirements = fetch_url(PYTORCH_MNIST_REQUIREMENTS)

    deep_lit = sentence_summary(read_text_or_path(deep_literature_review), max_sentences=2)

    # Parse key hyperparameters from main.py
    hyperparameters = {
        "batch_size": 64,
        "test_batch_size": 1000,
        "epochs": 14,
        "learning_rate": 1.0,
        "gamma": 0.7,
        "optimizer": "Adadelta",
        "dropout_1": 0.25,
        "dropout_2": 0.5,
        "seed": 1,
    }

    # Architecture summary
    architecture = {
        "conv1": "1 -> 32 filters, 3x3 kernel",
        "conv2": "32 -> 64 filters, 3x3 kernel",
        "dropout1": "p=0.25 (after conv layers)",
        "dropout2": "p=0.50 (after FC layer)",
        "fc1": "9216 -> 128",
        "fc2": "128 -> 10 (output)",
        "activation": "ReLU",
        "pooling": "MaxPool2d(2)",
    }

    proposal = f"""PROPOSAL SUMMARY
Research question: {research_question}
Repo: {repo_url}
Hypothesis: {hypothesis}

EXPERIMENT OVERVIEW:
This proposal outlines a replication study of the pytorch/examples MNIST CNN experiment.
The goal is to run the exact code from the repository and verify whether the reported
≥99% test accuracy is achievable within 14 training epochs.

REPOSITORY:
- URL: {repo_url}
- Key files:
  - mnist/main.py — training script
  - mnist/requirements.txt — dependencies

ARCHITECTURE:
{json.dumps(architecture, indent=2)}

HYPERPARAMETERS:
{json.dumps(hyperparameters, indent=2)}

DATASET:
- Name: MNIST Handwritten Digit Dataset
- Source: Auto-downloaded via torchvision.datasets.MNIST (no manual download needed)
- Train: 60,000 images
- Test: 10,000 images
- Format: 28x28 grayscale images, 10 classes (digits 0-9)

REPLICATION STEPS:
1. Clone the repository:
   git clone https://github.com/pytorch/examples.git
2. Navigate to the MNIST directory:
   cd examples/mnist
3. Install dependencies:
   pip install -r requirements.txt
4. Run training:
   python main.py
5. Capture output: epoch-by-epoch loss and final test accuracy

SUCCESS CRITERIA:
- Test accuracy ≥ 99% within 14 epochs
- Training completes without errors
- Results are logged and captured for the paper

EXPECTED OUTPUT:
- Final test accuracy (target: ≥99%)
- Per-epoch training loss and test accuracy
- Total training time

REQUIREMENTS FILE CONTENTS:
{requirements if requirements else "Could not fetch requirements.txt"}

MAIN.PY EXCERPT (first 3000 chars):
{main_py[:3000] if main_py else "Could not fetch main.py"}

DEEP LITERATURE CONTEXT:
{deep_lit}
"""

    print("[Proposal Agent] Proposal generated successfully.")
    return proposal


if __name__ == "__main__":
    question = input("Enter research question: ")
    review = input("Enter deep literature review path or text: ")
    print(run_proposal_stage(question, review))
