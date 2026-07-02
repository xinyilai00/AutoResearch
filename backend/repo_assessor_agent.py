from __future__ import annotations

import os
import concurrent.futures

from dotenv import load_dotenv
load_dotenv()

try:
    from .repo_grader_agent import run_repo_grader_agent
    from .repo_selector_agent import run_repo_selector_agent
    from .progress import log
except ImportError:
    from repo_grader_agent import run_repo_grader_agent
    from repo_selector_agent import run_repo_selector_agent
    from progress import log


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def run_repo_assessor_agent(repos: list[dict], topic: str) -> dict | None:
    if not repos:
        log("[Repo Assessor] No repos to assess.")
        return None

    log(f"[Repo Assessor] Grading {len(repos)} repos in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(repos)) as executor:
        futures = {
            executor.submit(run_repo_grader_agent, repo, topic, GITHUB_TOKEN): repo
            for repo in repos
        }
        graded = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                graded.append(result)
            except Exception as e:
                repo = futures[future]
                log(f"[Repo Assessor] Grader failed for {repo.get('name', 'unknown')}: {e}")

    if not graded:
        log("[Repo Assessor] All graders failed.")
        return None

    selected = run_repo_selector_agent(graded, topic)
    if selected:
        log(f"[Repo Selector] Selected: {selected.get('name', 'unknown')}")
    return selected