from __future__ import annotations

import os
import base64
import concurrent.futures
import time
import requests

try:
    from .agent_api import call_agent_api_json
    from .config import JSON_AGENT_ID
    from .progress import log
except ImportError:
    from agent_api import call_agent_api_json
    from config import JSON_AGENT_ID
    from progress import log


from dotenv import load_dotenv
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

GITHUB_QUERY_PROMPT = """You are a GitHub search expert. Given a research topic, generate 10 short GitHub repository search queries.

Rules:
- Each query must be 2-4 words maximum
- Use technical terms that would appear in a GitHub repo name, description, or README
- Queries should vary in specificity — some broader, some narrower
- Do not use academic jargon or full sentences
- Do not use filler words like 'the', 'of', 'and', 'in', 'for'
- Return ONLY a JSON array of strings, no explanation, no preamble

Example for topic "image classification with CNNs":
["image classification pytorch", "CNN classifier", "convolutional neural network", "deep learning vision"]
"""

REPO_RANKER_PROMPT = """You are an expert research engineer evaluating GitHub repositories for use in an autonomous academic research pipeline.

The pipeline will:
1. Clone the repo
2. Read the README and source files
3. Write and run a Python experiment script
4. Parse numerical results for an academic paper

You will be given a research topic and a list of GitHub repositories — each with their name, description, and README content.

Your job is to select the 10 most suitable repositories based on:
- Relevance: Is this repo directly about the research topic? Repos that are only tangentially related (wrong domain, wrong modality, wrong task) must be rejected.
- Runnability: Can it realistically be cloned and run with a Python script? Repos requiring paid APIs, proprietary datasets, or extremely complex setup must be rejected.
- Experimentability: Does it expose functionality that can produce measurable numerical results (accuracy, loss, speed, etc.) suitable for an academic paper?
- Quality: Is it a real research or engineering project, not a toy, demo, or deprecated repo?

Be strict. It is better to return fewer than 10 repos than to include irrelevant or unreliable ones. If fewer than 10 repos meet the bar, return only those that do.

Return ONLY a JSON array of up to 10 objects, no explanation, no preamble:
[
  {
    "name": "owner/repo",
    "url": "https://github.com/owner/repo",
    "description": "one sentence description of what this repo does",
    "reason": "one sentence explaining why this repo meets the bar for the pipeline"
  }
]
"""


def generate_github_queries(topic: str) -> list[str]:
    prompt = f"{GITHUB_QUERY_PROMPT}\n\nResearch topic: {topic}"
    log("[Repo Finder] Generating GitHub search queries...")
    result = call_agent_api_json(prompt, "GitHub Query Generator")
    if not isinstance(result, list):
        log("[Repo Finder] Query generator did not return a list.")
        return []
    log(f"[Repo Finder] Generated queries: {result}")
    return result


def search_github(query: str, max_results: int = 25) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    params = {
        "q": query + " language:Python",
        "sort": "stars",
        "order": "desc",
        "per_page": max_results,
    }

    for attempt in range(3):
        try:
            response = requests.get(GITHUB_SEARCH_URL, headers=headers, params=params, timeout=15)
            if response.status_code != 200:
                log(f"[Repo Finder] GitHub API error {response.status_code}: {response.text[:200]}")
                return []
            items = response.json().get("items", [])
            return [
                {
                    "name": item["full_name"],
                    "url": item["html_url"],
                    "description": item.get("description") or "",
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language") or "",
                    "updated_at": item.get("updated_at", ""),
                }
                for item in items
            ]
        except Exception as e:
            log(f"[Repo Finder] GitHub search failed on attempt {attempt + 1}/3: {e}")
            if attempt < 2:
                time.sleep(2)

    log(f"[Repo Finder] GitHub search gave up after 3 attempts for query: {query}")
    return []


def search_all_queries(queries: list[str], results_per_query: int = 25, top_n: int = 25) -> list[dict]:
    all_repos: dict[str, dict] = {}

    for query in queries:
        results = search_github(query, max_results=results_per_query)
        for repo in results:
            if repo["name"] not in all_repos:
                all_repos[repo["name"]] = repo

    log(f"[Repo Finder] Total unique candidates across all queries: {len(all_repos)}")
    sorted_repos = sorted(all_repos.values(), key=lambda x: x["stars"], reverse=True)
    top = sorted_repos[:top_n]
    log(f"[Repo Finder] Taking top {len(top)} by stars for README fetching.")
    return top


def fetch_readme(repo_name: str) -> str:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo_name}/readme",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            content = r.json().get("content", "")
            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
            return decoded[:1000]
    except Exception:
        pass
    return ""


def fetch_readmes_parallel(candidates: list[dict], max_workers: int = 10) -> list[dict]:
    log(f"[Repo Finder] Fetching READMEs for {len(candidates)} repos in parallel...")

    def fetch(candidate):
        readme = fetch_readme(candidate["name"])
        return {**candidate, "readme": readme}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(fetch, candidates))

    readme_count = sum(1 for r in results if r["readme"])
    log(f"[Repo Finder] Successfully fetched {readme_count}/{len(candidates)} READMEs.")
    return results


def rank_repos_with_llm(topic: str, candidates: list[dict]) -> list[dict]:
    candidates_text = "\n\n".join(
        f"### {r['name']} ({r['stars']} stars)\n"
        f"Description: {r['description']}\n"
        f"README (truncated):\n{r.get('readme', '(no README available)')}"
        for r in candidates
    )

    prompt = f"""{REPO_RANKER_PROMPT}

Research topic: {topic}

GitHub repositories to evaluate:
{candidates_text}
"""

    log(f"[Repo Finder] Asking LLM to rank {len(candidates)} candidates with READMEs...")
    result = call_agent_api_json(prompt, "Repo Ranker")

    if not isinstance(result, list):
        log("[Repo Finder] LLM did not return a list.")
        return []

    return result[:10]


def run_repo_finder_agent(topic: str) -> list[dict]:
    queries = generate_github_queries(topic)
    if not queries:
        log("[Repo Finder] No queries generated, aborting.")
        return []

    candidates = search_all_queries(queries)
    if not candidates:
        log("[Repo Finder] No candidates found, aborting.")
        return []

    candidates = fetch_readmes_parallel(candidates)
    ranked = rank_repos_with_llm(topic, candidates)
    log(f"[Repo Finder] Done. Selected {len(ranked)} repos.")
    return ranked