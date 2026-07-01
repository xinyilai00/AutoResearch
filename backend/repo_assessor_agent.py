from __future__ import annotations

import os
import concurrent.futures

from dotenv import load_dotenv
load_dotenv()

try:
    from .repo_grader_agent import run_repo_grader_agent
    from .repo_selector_agent import run_repo_selector_agent
except ImportError:
    from repo_grader_agent import run_repo_grader_agent
    from repo_selector_agent import run_repo_selector_agent


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def run_repo_assessor_agent(repos: list[dict], topic: str) -> dict | None:
    """
    Takes list of repos from repo_finder_agent, grades all in parallel,
    then selects the single best one.
    Returns the winning repo dict with name, url, description, reason.
    """
    if not repos:
        print("[Repo Assessor] No repos to assess.")
        return None

    print(f"[Repo Assessor] Grading {len(repos)} repos in parallel...")
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
                print(f"[Repo Assessor] Graded: {result.get('repo')} — relevance {result.get('relevance_score')}/10, accessibility {result.get('accessibility_score')}/10")
            except Exception as e:
                repo = futures[future]
                print(f"[Repo Assessor] Grader failed for {repo.get('name', 'unknown')}: {e}")

    if not graded:
        print("[Repo Assessor] All graders failed.")
        return None

    return run_repo_selector_agent(graded, topic)