from __future__ import annotations

import requests

try:
    from .agent_api import call_agent_api_json
    from .config import REPO_GRADER_PRINCIPAL_ID, JSON_AGENT_ID
    from .progress import log
except ImportError:
    from agent_api import call_agent_api_json
    from config import REPO_GRADER_PRINCIPAL_ID, JSON_AGENT_ID
    from progress import log


GRADER_PROMPT = """You are an expert research engineer assessing a GitHub repository for use in an autonomous academic research pipeline.

PIPELINE CONSTRAINTS (critical context for your assessment):
- Runs on a standard CPU laptop with no GPU, no CUDA, no display server
- Dependencies must be pip-installable without system-level build tools
- The experiment script must complete and produce numerical results in under 10 minutes on CPU
- No Docker, no proprietary data, no paid APIs
- Results must be printed to stdout as numbers (accuracy, loss, score, etc.)

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

ACCESSIBILITY: How easy is it to run a meaningful experiment from this repo within the pipeline constraints above? Score each sub-factor mentally before giving a final score:

  - Compute requirements (heavy penalty if GPU/CUDA required to produce ANY results; heavy penalty if JAX XLA acceleration is required; moderate penalty if training takes hours even on GPU)
  - System dependencies (heavy penalty if EGL, OSMesa, X11, Warp, or other display/graphics backends are required with no CPU fallback; moderate penalty for complex C extensions or custom build steps)
  - Install complexity (moderate penalty if install requires more than standard pip; moderate penalty if many large dependencies like PyTorch + torchvision + transformers all required together)
  - Runtime feasibility (heavy penalty if README or code indicates GPU strongly recommended or required for meaningful results; heavy penalty if minimum meaningful experiment takes more than 10 minutes on CPU)
  - Output clarity (moderate penalty if results are only written to files in unpredictable formats with no stdout output; no penalty if results are printed to stdout)

Scoring guide for accessibility:
- 8-10: Pure Python, pip-installable, CPU-runnable in under 5 minutes, clear stdout output
- 5-7: Some complexity but workable — small C extensions, moderate dependencies, 5-10 min runtime
- 3-4: Significant barriers — GPU helpful but not strictly required, complex install, borderline runtime
- 1-2: GPU required for any meaningful results, OR requires display server with no CPU fallback, OR takes hours even on GPU

Hard disqualification flags (set to true only when 99.9% certain the pipeline cannot run this):
- requires_proprietary_data: only if data is genuinely unavailable without payment or institutional access
- requires_display_server: only if a display/graphics backend (EGL, OSMesa, X11, Warp) is required AND there is NO documented CPU or headless fallback path anywhere in the README or source files

Output ONLY a JSON object in exactly this format, no explanation, no preamble:
{
  "repo": "owner/repo",
  "relevance_score": <integer 1-10>,
  "relevance_reason": "<one sentence explaining the relevance score>",
  "accessibility_score": <integer 1-10>,
  "accessibility_reason": "<one sentence explaining the accessibility score, mentioning the key factors that drove the score>",
  "overall_assessment": "<one sentence overall assessment of this repo's suitability for the pipeline>",
  "has_clear_entrypoint": <true or false>,
  "requires_proprietary_data": <true or false>,
  "requires_display_server": <true or false>,
  "is_deprecated": <true or false>
}
"""


def get_github_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}" if token else "",
    }


def fetch_file_tree(repo_name: str, token: str) -> str:
    headers = get_github_headers(token)
    for branch in ["main", "master"]:
        url = f"https://api.github.com/repos/{repo_name}/git/trees/{branch}?recursive=1"
        try:
            r = requests.get(url, headers=headers, timeout=10)
        except requests.RequestException as exc:
            log(f"[Repo Grader] File tree fetch failed for {repo_name}@{branch}: {exc}")
            continue
        if r.status_code == 200:
            items = r.json().get("tree", [])
            files = [item["path"] for item in items if item["type"] == "blob"]
            return "\n".join(files[:100])
    return ""


def fetch_readme(repo_name: str, token: str) -> str:
    import base64
    headers = get_github_headers(token)
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo_name}/readme",
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        log(f"[Repo Grader] README fetch failed for {repo_name}: {exc}")
        return ""
    if r.status_code == 200:
        content = r.json().get("content", "")
        decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        return decoded[:3000]
    return ""


def fetch_source_files(repo_name: str, file_tree: str, topic: str, token: str) -> str:
    headers = get_github_headers(token)

    file_selection_prompt = f"""Given this research topic and file tree, list up to 6 file paths that are most important for understanding how to run experiments with this repository.

Research topic: {topic}

File tree:
{file_tree}

Return ONLY a JSON array of file path strings, no explanation.
Example: ["main.py", "src/model.py", "train.py"]
"""
    try:
        selected = call_agent_api_json(file_selection_prompt, "File Selector")
    except Exception as exc:
        log(f"[Repo Grader] File Selector failed for {repo_name}: {exc}")
        return ""
    if not isinstance(selected, list):
        return ""

    contents = []
    for path in selected[:6]:
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{repo_name}/{branch}/{path}"
            try:
                r = requests.get(url, headers=headers, timeout=10)
            except requests.RequestException as exc:
                log(f"[Repo Grader] Source fetch failed for {repo_name}/{path}@{branch}: {exc}")
                continue
            if r.status_code == 200:
                contents.append(f"### {path}\n{r.text[:1000]}")
                break

    return "\n\n".join(contents)


def grade_repo(repo: dict, topic: str, token: str) -> dict:
    repo_name = repo["name"]
    log(f"[Repo Grader] Grading {repo_name}...")

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

    result = call_agent_api_json(prompt, f"Grader {repo_name}")
    if not isinstance(result, dict):
        log(f"[Repo Grader] Invalid response for {repo_name}")
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
            "requires_display_server": False,
            "is_deprecated": True,
        }

    result["url"] = repo.get("url", "")
    result["description"] = repo.get("description", "")
    log(f"[Repo Grader] Graded {repo_name} — relevance {result.get('relevance_score')}/10, accessibility {result.get('accessibility_score')}/10")
    return result


def run_repo_grader_agent(repo: dict, topic: str, token: str) -> dict:
    return grade_repo(repo, topic, token)