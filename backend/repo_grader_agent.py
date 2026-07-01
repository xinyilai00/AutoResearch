from __future__ import annotations

import requests

try:
    from .agent_api import call_agent_api_json
    from .config import REPO_GRADER_PRINCIPAL_ID, JSON_AGENT_ID
except ImportError:
    from agent_api import call_agent_api_json
    from config import REPO_GRADER_PRINCIPAL_ID, JSON_AGENT_ID


GRADER_PROMPT = """You are an expert research engineer assessing a GitHub repository for use in an autonomous academic research pipeline.

The pipeline will:
1. Clone the repo
2. Read the README and source files
3. Write and run a Python experiment script
4. Parse numerical results for an academic paper

You will be given:
- A research topic
- The repo's README
- The repo's file tree
- Up to 6 key source files

Your job is to assess this repo on two dimensions:

RELEVANCE: How directly does this repo relate to the research topic? Consider whether the core functionality, datasets, and methods match what the research topic requires.

ACCESSIBILITY: How easy is it to clone, install, and run an experiment script against this repo? Consider: clear README instructions, pip-installable dependencies, no proprietary data requirements, clear entry points, active maintenance, not deprecated/archived.

Output ONLY a JSON object in exactly this format, no explanation, no preamble:
{
  "repo": "owner/repo",
  "relevance_score": <integer 1-10>,
  "relevance_reason": "<one sentence explaining the relevance score>",
  "accessibility_score": <integer 1-10>,
  "accessibility_reason": "<one sentence explaining the accessibility score>",
  "overall_assessment": "<one sentence overall assessment of this repo's suitability for the pipeline>",
  "has_clear_entrypoint": <true or false>,
  "requires_proprietary_data": <true or false>,
  "is_deprecated": <true or false>
}
"""


GITHUB_HEADERS_CACHE: dict = {}


def get_github_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}" if token else "",
    }


def fetch_file_tree(repo_name: str, token: str) -> str:
    """Fetch file tree for a repo, trying main then master branch."""
    headers = get_github_headers(token)
    for branch in ["main", "master"]:
        url = f"https://api.github.com/repos/{repo_name}/git/trees/{branch}?recursive=1"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            items = r.json().get("tree", [])
            files = [item["path"] for item in items if item["type"] == "blob"]
            return "\n".join(files[:100])  # cap at 100 files
    return ""


def fetch_readme(repo_name: str, token: str) -> str:
    """Fetch README content for a repo."""
    import base64
    headers = get_github_headers(token)
    r = requests.get(
        f"https://api.github.com/repos/{repo_name}/readme",
        headers=headers,
        timeout=10,
    )
    if r.status_code == 200:
        content = r.json().get("content", "")
        decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        return decoded[:3000]
    return ""


def fetch_source_files(repo_name: str, file_tree: str, topic: str, token: str) -> str:
    """Ask LLM which source files to read, then fetch their contents."""
    headers = get_github_headers(token)

    # Ask LLM which files to read
    file_selection_prompt = f"""Given this research topic and file tree, list up to 6 file paths that are most important for understanding how to run experiments with this repository.

Research topic: {topic}

File tree:
{file_tree}

Return ONLY a JSON array of file path strings, no explanation.
Example: ["main.py", "src/model.py", "train.py"]
"""
    selected = call_agent_api_json(file_selection_prompt, "File Selector")
    if not isinstance(selected, list):
        return ""

    contents = []
    for path in selected[:6]:
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{repo_name}/{branch}/{path}"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                contents.append(f"### {path}\n{r.text[:1000]}")
                break

    return "\n\n".join(contents)


def grade_repo(repo: dict, topic: str, token: str) -> dict:
    """Grade a single repo for relevance and accessibility."""
    repo_name = repo["name"]
    print(f"[Repo Grader] Grading {repo_name}...")

    readme = fetch_readme(repo_name, token)
    file_tree = fetch_file_tree(repo_name, token)
    source_files = fetch_source_files(repo_name, file_tree, topic, token)

    prompt = f"""{GRADER_PROMPT}

Research topic: {topic}

Repository: {repo_name}
Description: {repo.get('description', '')}

README:
{readme}

File tree:
{file_tree}

Key source files:
{source_files}
"""

    result = call_agent_api_json(prompt, f"Grader {repo_name}", )
    if not isinstance(result, dict):
        print(f"[Repo Grader] Invalid response for {repo_name}")
        return {
            "repo": repo_name,
            "url": repo.get("url", ""),
            "relevance_score": 0,
            "relevance_reason": "Grader failed to assess.",
            "accessibility_score": 0,
            "accessibility_reason": "Grader failed to assess.",
            "overall_assessment": "Assessment unavailable.",
            "has_clear_entrypoint": False,
            "requires_proprietary_data": True,
            "is_deprecated": True,
        }

    result["url"] = repo.get("url", "")
    result["description"] = repo.get("description", "")
    return result


def run_repo_grader_agent(repo: dict, topic: str, token: str) -> dict:
    """Main entry point for grading a single repo."""
    return grade_repo(repo, topic, token)