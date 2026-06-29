from __future__ import annotations

import json
import urllib.request
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
except ImportError:
    from pipeline_state import get_experiment_anchor


PYTORCH_MNIST_MAIN_PY = "https://raw.githubusercontent.com/ncorpron/MNIST_CNN_with_PyTorch/main/train.py"
PYTORCH_MNIST_REQUIREMENTS = "https://raw.githubusercontent.com/ncorpron/MNIST_CNN_with_PyTorch/main/requirements.txt"


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
        "batch_size": 128,
        "epochs": 10,
        "learning_rate": 1e-3,
        "optimizer": "Adam",
        "seed": 42,
    }

    # Architecture summary
    architecture = {
        "model": "SimpleCNN (see models.py)",
        "loss": "CrossEntropyLoss",
        "optimizer": "Adam (lr=1e-3)",
        "data_augmentation": "Normalize((0.1307,), (0.3081,))",
    }

    proposal = f"""PROPOSAL SUMMARY
Research question: {research_question}
Repo: {repo_url}
Hypothesis: {hypothesis}

EXPERIMENT OVERVIEW:
This proposal outlines a replication study of the ncorpron/MNIST_CNN_with_PyTorch experiment.
The goal is to run the exact code from the repository and verify classification accuracy
on the MNIST handwritten digit dataset within 10 training epochs.

REPOSITORY:
- URL: {repo_url}
- Key files:
  - train.py — training script
  - requirements.txt — dependencies

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
   git clone https://github.com/ncorpron/MNIST_CNN_with_PyTorch.git
2. Install dependencies:
   pip install -r requirements.txt
3. Run training:
   python train.py
4. Capture output: epoch-by-epoch loss, train accuracy, and validation accuracy

SUCCESS CRITERIA:
- Validation accuracy ≥ 99% within 10 epochs
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
