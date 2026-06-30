from __future__ import annotations

import json
import urllib.request
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
    from backend.repo_library import get_repo_by_id, select_repo_for_prompt
    from backend.agent_api import call_agent_api, call_agent_api_json
    from backend.experiment_agent import sanitize_setup
except ImportError:
    from pipeline_state import get_experiment_anchor
    from repo_library import get_repo_by_id, select_repo_for_prompt
    from agent_api import call_agent_api, call_agent_api_json
    from experiment_agent import sanitize_setup

RAW_GITHUB_BASE = "https://raw.githubusercontent.com"
GITHUB_API_BASE = "https://api.github.com"

PROPOSAL_SYSTEM_PROMPT = """You are a research engineer in an autonomous research pipeline. You will be given a GitHub repository README and file tree.

Your job is to produce a JSON object describing exactly how to run an experiment from this repository.

RULES:
- Reply with JSON only. No explanation, no markdown fences, no preamble, no reasoning text of any kind.
- Your entire response must be valid JSON starting with { and ending with }. Nothing else.
- Do NOT write sentences like "I'll now..." or "Let me...". Output ONLY the JSON object.
- You are NOT executing any code or installing any packages. You are only writing instructions in JSON format that describe what SHOULD be run later by someone else. Never report fake "success" or "output" results — only describe the setup.
- install_commands: list of pip package names to install, WITHOUT version pins. e.g. ["numpy", "pandas", "nab"]. Do not include "pip install" prefix.
- run_script: a complete, valid, standalone Python script as a single string that runs the experiment and prints results to stdout. Use only packages from install_commands. Must be runnable as-is. CRITICAL: when printing any result, score, or metric, always print it on its own clearly labeled line in the exact format "RESULT: <name/identifier> | <metric name> | <value>" so that automated parsing can unambiguously map each number to exactly what it measured. Do this for every individual result, not just a summary.
- data_setup_commands: list of shell commands to download or prepare data. Empty list if data is already included in the repo.
- expected_metric: the primary metric name to look for in stdout.
- notes: any important caveats about running this repo.
- IMPORTANT FOR SPEED: if the repository involves running multiple algorithms or detectors across a dataset, choose only 2-3 representative options and/or use the smallest available test dataset/subset mentioned in the README, so the experiment completes in under 2 minutes. Do not run the full evaluation suite.

Example output:
{
  "install_commands": ["numpy", "pandas", "nab"],
  "run_script": "from nab.runner import Runner\\nfrom nab.detectors.null.null_detector import NullDetector\\nrunner = Runner(dataDir='data', resultsDir='results', labelPath='labels/combined_windows.json', profilesPath='config/profiles.json', thresholdPath='config/thresholds.json')\\nrunner.initialize()\\nrunner.detect({'null': NullDetector})\\nthresholds = runner.optimize(['null'])\\nrunner.score(['null'], thresholds)\\nrunner.normalize()",
  "data_setup_commands": [],
  "expected_metric": "NAB score",
  "notes": "Data is included in the repo. Results written to results/final_results.json."
}
"""


def fetch_url(url: str, headers: dict = {}) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AutoResearch-Proposal", **headers})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"[Proposal Agent] Failed to fetch {url}: {e}")
        return ""


def fetch_raw_file(repo_name: str, filename: str) -> str:
    for branch in ("main", "master"):
        url = f"{RAW_GITHUB_BASE}/{repo_name}/{branch}/{filename}"
        content = fetch_url(url)
        if content.strip():
            print(f"[Proposal Agent] Fetched {url}")
            return content
        else:
            print(f"[Proposal Agent] Empty or failed: {url}")
    return ""


def fetch_file_tree(repo_name: str) -> list[str]:
    for branch in ("main", "master"):
        url = f"{GITHUB_API_BASE}/repos/{repo_name}/git/trees/{branch}?recursive=1"
        content = fetch_url(url)
        if content:
            try:
                data = json.loads(content)
                files = [item["path"] for item in data.get("tree", []) if item["type"] == "blob"]
                if files:
                    print(f"[Proposal Agent] Fetched file tree from {url} ({len(files)} files)")
                    return files
            except Exception as e:
                print(f"[Proposal Agent] Failed to parse file tree from {url}: {e}")
        else:
            print(f"[Proposal Agent] Empty or failed: {url}")
    return []

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

def run_proposal_stage(research_question: str, deep_literature_review: str | Path) -> str:
    print("\n[Proposal Agent] Starting proposal generation...")
    anchor = get_experiment_anchor()
    repo_id = anchor.get("repo_id", "")
    repo_url = anchor["repo_url"]
    hypothesis = anchor["hypothesis"]

    selected_repo = get_repo_by_id(repo_id) or select_repo_for_prompt(research_question)
    repo_name = selected_repo["name"]

    print(f"[Proposal Agent] Fetching README and file tree for {repo_name}...")
    readme = fetch_raw_file(repo_name, "README.md") or fetch_raw_file(repo_name, "README.rst")
    file_tree = fetch_file_tree(repo_name)
    file_tree_str = "\n".join(file_tree[:200])

    # STEP 1: Ask which files are needed to write a correct, verified run script
    print("[Proposal Agent] Identifying relevant source files...")
    file_selection = call_agent_api_json(
        f"You are a research engineer planning an experiment using a GitHub repository.\n\n"
        f"Research question: {research_question}\n\n"
        f"Repository: {repo_url}\n\n"
        f"README:\n{readme[:3000]}\n\n"
        f"File tree:\n{file_tree_str}\n\n"
        f"RULES:\n"
        f"- Reply with JSON only, no explanation, no markdown fences.\n"
        f"- Identify up to 6 specific file paths (from the file tree above, exact paths) whose ACTUAL CONTENTS you need to read "
        f"before you can write a correct Python script that imports and uses this repo's code correctly. "
        f"This should include the main entrypoint/runner file and any specific modules/classes you plan to import and use directly.\n"
        f"- Output format: {{\"files_needed\": [\"path/to/file1.py\", \"path/to/file2.py\"]}}",
        label="FileSelection",
    )
    files_needed = file_selection.get("files_needed", []) if file_selection else []
    files_needed = files_needed[:6]  # cap for prompt size

    print(f"[Proposal Agent] Fetching contents of {len(files_needed)} source file(s)...")
    source_contents = {}
    for file_path in files_needed:
        content = fetch_raw_file(repo_name, file_path)
        if content:
            source_contents[file_path] = content[:3000]  # cap per-file size

    source_context = "\n\n".join(
        f"=== FILE: {path} ===\n{content}" for path, content in source_contents.items()
    )

    # STEP 2: Generate the actual run script using verified source code
    print("[Proposal Agent] Generating experiment setup using verified source code...")
    raw_setup = call_agent_api_json(
        PROPOSAL_SYSTEM_PROMPT +
        f"\nResearch question: {research_question}\n\n"
        f"Repository: {repo_url}\n\n"
        f"README:\n{readme[:2000]}\n\n"
        f"ACTUAL SOURCE CODE of relevant files (use these exact class/function names, do not guess):\n{source_context}",
        label="ProposalReasoning",
    )

    if not raw_setup or not raw_setup.get("run_script"):
        raise RuntimeError(
            f"[Proposal Agent] Could not generate a valid experiment setup for {repo_name}. "
            f"Refusing to proceed with an empty/fake setup."
        )

    setup = sanitize_setup(raw_setup)

    proposal = f"""PROPOSAL SUMMARY
Research question: {research_question}
Repo: {repo_url}
Hypothesis: {hypothesis}

EXPERIMENT SETUP JSON:
{json.dumps(setup, indent=2)}

NOTES:
{setup.get('notes', '')}
"""

    print("[Proposal Agent] Proposal generated successfully.")
    return proposal

if __name__ == "__main__":
    question = input("Enter research question: ")
    review = input("Enter deep literature review path or text: ")
    print(run_proposal_stage(question, review))