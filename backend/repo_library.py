from __future__ import annotations

import re
from typing import Any


RepoMetadata = dict[str, Any]


REPO_LIBRARY: list[RepoMetadata] = [
    {
        "id": "mnist_cnn_pytorch",
        "name": "ncorpron/MNIST_CNN_with_PyTorch",
        "url": "https://github.com/ncorpron/MNIST_CNN_with_PyTorch",
        "domains": ["computer vision", "image classification", "deep learning"],
        "tasks": ["MNIST digit classification", "CNN replication", "accuracy benchmark"],
        "datasets": [
            {
                "name": "MNIST",
                "source": "torchvision.datasets.MNIST",
                "access": "auto-download",
                "size": "60,000 train images, 10,000 test images",
            }
        ],
        "metrics": ["validation accuracy", "test accuracy", "training loss"],
        "dependencies": ["python", "torch", "torchvision"],
        "entrypoints": ["train.py"],
        "requirements_files": ["requirements.txt"],
        "source_files": ["train.py", "README.md"],
        "benchmark_notes": "Good small image-classification benchmark with a clear >=99% accuracy target.",
        "best_for_prompts": [
            "replicate a CNN on MNIST",
            "benchmark digit classification accuracy",
            "test a simple PyTorch computer vision model",
        ],
        "keywords": [
            "mnist", "digit", "digits", "cnn", "image", "classification", "torch",
            "pytorch", "vision", "handwritten", "accuracy",
        ],
        "difficulty": "medium",
    },
    {
        "id": "pmlb",
        "name": "EpistasisLab/pmlb",
        "url": "https://github.com/EpistasisLab/pmlb",
        "domains": ["tabular machine learning", "classification", "regression"],
        "tasks": ["tabular classification", "tabular regression", "model comparison"],
        "datasets": [
            {
                "name": "PMLB benchmark datasets",
                "source": "PMLB Python API / curated dataset files",
                "access": "API or local cache",
                "size": "Many small-to-medium tabular datasets",
            }
        ],
        "metrics": ["accuracy", "F1", "ROC AUC", "RMSE", "MAE", "R2"],
        "dependencies": ["python", "pandas", "scikit-learn", "pmlb"],
        "entrypoints": ["Python API examples"],
        "requirements_files": ["pyproject.toml", "setup.py", "requirements.txt"],
        "source_files": ["README.md", "docs/usage.md", "pmlb/__init__.py"],
        "benchmark_notes": "Strong default for non-image tabular benchmark studies.",
        "best_for_prompts": [
            "compare classifiers on tabular benchmark data",
            "benchmark regression models across public datasets",
            "evaluate classical ML methods on curated datasets",
        ],
        "keywords": [
            "tabular", "classification", "regression", "sklearn", "scikit", "pandas",
            "benchmark", "datasets", "classifier", "regressor", "auc", "rmse", "f1",
        ],
        "difficulty": "low",
    },
    {
        "id": "numenta_nab",
        "name": "numenta/NAB",
        "url": "https://github.com/numenta/NAB",
        "domains": ["time series", "anomaly detection", "streaming data"],
        "tasks": ["anomaly detection", "streaming benchmark", "event detection"],
        "datasets": [
            {
                "name": "Numenta Anomaly Benchmark datasets",
                "source": "NAB data CSV files",
                "access": "included in repository",
                "size": "Labeled real and artificial time-series streams",
            }
        ],
        "metrics": ["NAB score", "precision", "recall", "F1", "detection delay"],
        "dependencies": ["python", "numpy", "pandas"],
        "entrypoints": ["run.py", "benchmark scripts"],
        "requirements_files": ["requirements.txt", "setup.py"],
        "source_files": ["README.md", "run.py", "nab/runner.py"],
        "benchmark_notes": "Good fit for anomaly detection prompts where labels and scoring matter.",
        "best_for_prompts": [
            "detect anomalies in server metrics",
            "benchmark streaming anomaly detection",
            "compare detectors on labeled time-series data",
        ],
        "keywords": [
            "anomaly", "anomalies", "time", "series", "timeseries", "stream", "streaming",
            "sensor", "server", "metric", "detection", "nab", "forecast", "outlier",
        ],
        "difficulty": "medium",
    },
    {
        "id": "implicit_recommenders",
        "name": "benfred/implicit",
        "url": "https://github.com/benfred/implicit",
        "domains": ["recommender systems", "implicit feedback", "ranking"],
        "tasks": ["collaborative filtering", "item recommendation", "ranking benchmark"],
        "datasets": [
            {
                "name": "MovieLens / implicit-feedback datasets",
                "source": "examples and user-provided interaction matrices",
                "access": "download or local sparse matrix",
                "size": "Small-to-large user-item interaction data",
            }
        ],
        "metrics": ["precision@k", "MAP@k", "NDCG@k", "AUC", "recommendation latency"],
        "dependencies": ["python", "numpy", "scipy", "implicit"],
        "entrypoints": ["examples", "Python API"],
        "requirements_files": ["pyproject.toml", "setup.py", "requirements.txt"],
        "source_files": ["README.md", "examples/lastfm.py", "examples/movielens.py"],
        "benchmark_notes": "Focused library for fast implicit-feedback recommender experiments.",
        "best_for_prompts": [
            "recommend items from user interaction logs",
            "benchmark collaborative filtering on MovieLens",
            "compare ALS and nearest-neighbor recommenders",
        ],
        "keywords": [
            "recommend", "recommendation", "recommender", "ranking", "movielens", "movie",
            "user", "item", "collaborative", "filtering", "implicit", "als", "ndcg", "map",
        ],
        "difficulty": "medium",
    },
]


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def score_repo_for_prompt(repo: RepoMetadata, prompt: str) -> int:
    prompt_tokens = tokenize(prompt)
    score = 0

    for keyword in repo.get("keywords", []):
        keyword_tokens = tokenize(keyword)
        if keyword_tokens and keyword_tokens.issubset(prompt_tokens):
            score += 4 if len(keyword_tokens) > 1 else 2

    searchable_fields = [
        *repo.get("domains", []),
        *repo.get("tasks", []),
        *repo.get("metrics", []),
        *repo.get("best_for_prompts", []),
    ]
    for field in searchable_fields:
        overlap = tokenize(field) & prompt_tokens
        score += len(overlap)

    return score


def select_repo_for_prompt(prompt: str) -> RepoMetadata:
    return max(REPO_LIBRARY, key=lambda repo: score_repo_for_prompt(repo, prompt))


def get_repo_by_id(repo_id: str) -> RepoMetadata | None:
    for repo in REPO_LIBRARY:
        if repo["id"] == repo_id:
            return repo
    return None


def format_repo_metadata(repo: RepoMetadata) -> str:
    datasets = ", ".join(dataset["name"] for dataset in repo.get("datasets", []))
    return "\n".join(
        [
            f"- Selected repo: {repo['name']}",
            f"- URL: {repo['url']}",
            f"- Domains: {', '.join(repo['domains'])}",
            f"- Tasks: {', '.join(repo['tasks'])}",
            f"- Datasets: {datasets}",
            f"- Metrics: {', '.join(repo['metrics'])}",
            f"- Dependencies: {', '.join(repo['dependencies'])}",
            f"- Requirement/config candidates: {', '.join(repo.get('requirements_files', []))}",
            f"- Source/example candidates: {', '.join(repo.get('source_files', []))}",
            f"- Difficulty: {repo['difficulty']}",
            f"- Fit notes: {repo['benchmark_notes']}",
        ]
    )
