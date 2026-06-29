from __future__ import annotations

import json
import urllib.request
from pathlib import Path

try:
    from backend.pipeline_state import get_experiment_anchor
    from backend.repo_library import get_repo_by_id, select_repo_for_prompt
    from backend.agent_api import call_agent_api
except ImportError:
    from pipeline_state import get_experiment_anchor
    from repo_library import get_repo_by_id, select_repo_for_prompt
    from agent_api import call_agent_api

RAW_GITHUB_BASE = "https://raw.githubusercontent.com"
GITHUB_API_BASE = "https://api.github.com"

PROPOSAL_SYSTEM_PROMPT = """You are a research engineer in an autonomous research pipeline. You will be given a GitHub repository README and file tree.

Your job is to produce a JSON object describing exactly how to run an experiment from this repository.

RULES:
- Reply with JSON only. No explanation, no markdown fences, no preamble.
- install_commands: list of pip package names to install, WITHOUT version pins. e.g. ["numpy", "pandas", "nab"]. Do not include "pip install" prefix.
- run_script: a complete, valid, standalone Python script as a single string that runs the experiment and prints results to stdout. Use only packages from install_commands. Must be runnable as-is.
- data_setup_commands: list of shell commands to download or prepare data. Empty list if data is already included in the repo.
- expected_metric: the primary metric name to look for in stdout.
- notes: any important caveats about running this repo.

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

def sanitize_setup(setup: dict) -> dict:
    # Remove data_setup_commands that involve cloning or cd — experiment agent handles cloning
    setup["data_setup_commands"] = [
        cmd for cmd in setup.get("data_setup_commands", [])
        if not any(skip in cmd for skip in ["git clone", "cd ", "pip install ."])
    ]

    # Fix run_script — remove any os.chdir() and path manipulation assuming a subdirectory
    # The script runs from CLONE_DIR directly, so no subdirectory navigation needed
    script = setup.get("run_script", "")
    fixed_lines = []
    for line in script.split("\n"):
        if "os.chdir" in line:
            continue
        if "nab_dir" in line and ("os.path.join" in line or "sys.path" in line):
            continue
        if "sys.path.insert" in line:
            continue
        line = line.replace("nab_dir", "os.getcwd()")
        line = line.replace("'NAB/", "'")
        line = line.replace('"NAB/', '"')
        fixed_lines.append(line)
    setup["run_script"] = "\n".join(fixed_lines)

    # Remove earthgeckoSkyline — too slow
    setup["run_script"] = setup["run_script"].replace(
        "from nab.detectors.earthgecko_skyline.earthgecko_skyline_detector import EarthgeckoSkylineDetector\n", ""
    ).replace(
        "    'earthgeckoSkyline': EarthgeckoSkylineDetector,\n", ""
    )

    # Remove Cython from install_commands — incompatible with Python 3.13
    setup["install_commands"] = [
        pkg for pkg in setup.get("install_commands", [])
        if pkg.lower() not in {"cython"}
    ]

    return setup


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

    print("[Proposal Agent] Asking agent to reason about repo setup and execution...")
    raw_response = call_agent_api(
        PROPOSAL_SYSTEM_PROMPT +
        f"\nResearch question: {research_question}\n\n"
        f"Repository: {repo_url}\n\n"
        f"README:\n{readme[:4000]}\n\n"
        f"File tree:\n{file_tree_str}",
        label="ProposalReasoning",
    ).strip()

    # Parse and validate the JSON
    try:
        clean = raw_response.replace("```json", "").replace("```", "").strip()
        setup = sanitize_setup(json.loads(clean))
    except Exception as e:
        print(f"[Proposal Agent] Warning: could not parse JSON response: {e}")
        print(f"[Proposal Agent] Raw response was: {raw_response[:500]}")
        setup = {
            "install_commands": [],
            "run_script": "",
            "data_setup_commands": [],
            "expected_metric": "benchmark performance",
            "notes": "Could not parse setup instructions.",
        }

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