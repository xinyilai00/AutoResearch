from __future__ import annotations

from typing import Any

try:
    from backend.agent_api import call_agent_api
except ImportError:
    from agent_api import call_agent_api

RepoMetadata = dict[str, Any]

REPO_LIBRARY: list[RepoMetadata] = [
    {"id": "mnist_cnn_pytorch", "name": "ncorpron/MNIST_CNN_with_PyTorch", "url": "https://github.com/ncorpron/MNIST_CNN_with_PyTorch", "description": "CNN image classification on MNIST handwritten digits"},
    {"id": "pmlb", "name": "EpistasisLab/pmlb", "url": "https://github.com/EpistasisLab/pmlb", "description": "tabular ML classification and regression benchmarks"},
    {"id": "numenta_nab", "name": "numenta/NAB", "url": "https://github.com/numenta/NAB", "description": "streaming time series anomaly detection benchmark"},
    {"id": "implicit_recommenders", "name": "benfred/implicit", "url": "https://github.com/benfred/implicit", "description": "implicit feedback collaborative filtering recommender systems"},
]


def select_repo_for_prompt(prompt: str) -> RepoMetadata:
    options = "\n".join(
        f"- id: {r['id']} | url: {r['url']} | description: {r['description']}"
        for r in REPO_LIBRARY
    )
    response = call_agent_api(
        f"Given this research topic or prompt:\n{prompt}\n\n"
        f"Select the most relevant repository from this list:\n{options}\n\n"
        f"Reply with only the repo id, nothing else.",
        label="RepoSelector",
    ).strip().lower()

    for repo in REPO_LIBRARY:
        if repo["id"] in response:
            return repo

    return REPO_LIBRARY[0]


def get_repo_by_id(repo_id: str) -> RepoMetadata | None:
    for repo in REPO_LIBRARY:
        if repo["id"] == repo_id:
            return repo
    return None