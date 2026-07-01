from __future__ import annotations

try:
    from .agent_api import call_agent_api_json
    from .config import REPO_SELECTOR_PRINCIPAL_ID, JSON_AGENT_ID
except ImportError:
    from agent_api import call_agent_api_json
    from config import REPO_SELECTOR_PRINCIPAL_ID, JSON_AGENT_ID


SELECTOR_PROMPT = """You are an expert research engineer selecting the single best GitHub repository for an autonomous academic research pipeline.

The pipeline will:
1. Clone the repo
2. Read the README and source files
3. Write and run a Python experiment script
4. Parse numerical results for an academic paper

You will be given a research topic and a list of graded repositories, each with:
- Relevance score (1-10) and reason
- Accessibility score (1-10) and reason
- Overall assessment
- Boolean flags: has_clear_entrypoint, requires_proprietary_data, is_deprecated

Your job is to select the SINGLE best repository. Use holistic judgment — do not just pick the highest average score. A highly relevant repo that is slightly harder to run is better than an easy-to-run repo that barely matches the topic. Immediately disqualify any repo where requires_proprietary_data is true or is_deprecated is true.

Output ONLY a JSON object in exactly this format, no explanation, no preamble:
{
  "name": "owner/repo",
  "url": "https://github.com/owner/repo",
  "description": "one sentence description of what this repo does",
  "reason": "two to three sentences explaining why this repo was selected over the others"
}
"""


def run_repo_selector_agent(graded_repos: list[dict], topic: str) -> dict | None:
    """
    Takes a list of graded repo dicts from repo_grader_agent.
    Returns the single best repo as a dict with name, url, description, reason.
    """
    if not graded_repos:
        print("[Repo Selector] No graded repos to select from.")
        return None

    repos_text = "\n\n".join(
        f"### {r.get('repo', 'unknown')}\n"
        f"URL: {r.get('url', '')}\n"
        f"Description: {r.get('description', '')}\n"
        f"Relevance: {r.get('relevance_score', 0)}/10 — {r.get('relevance_reason', '')}\n"
        f"Accessibility: {r.get('accessibility_score', 0)}/10 — {r.get('accessibility_reason', '')}\n"
        f"Overall: {r.get('overall_assessment', '')}\n"
        f"Has clear entrypoint: {r.get('has_clear_entrypoint', False)}\n"
        f"Requires proprietary data: {r.get('requires_proprietary_data', True)}\n"
        f"Is deprecated: {r.get('is_deprecated', False)}"
        for r in graded_repos
    )

    prompt = f"""{SELECTOR_PROMPT}

Research topic: {topic}

Graded repositories:
{repos_text}
"""

    print(f"[Repo Selector] Selecting best repo from {len(graded_repos)} graded candidates...")
    result = call_agent_api_json(prompt, "Repo Selector")

    if not isinstance(result, dict):
        print("[Repo Selector] Invalid response from selector agent:", result)
        return None

    print(f"[Repo Selector] Selected: {result.get('name', 'unknown')}")
    return result