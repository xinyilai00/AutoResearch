from __future__ import annotations

import json
from pathlib import Path

import requests
from dotenv import load_dotenv

from backend.config import API_KEY, BASE_URL


PROJECT_ROOT = Path(__file__).parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

PRINCIPALS = {
    "PROPOSAL_PRINCIPAL_ID": (
        "proposal-agent",
        "Principal for proposal orchestration stage",
    ),
    "HYPOTHESIS_PRINCIPAL_ID": (
        "hypothesis-agent",
        "Principal for hypothesis generation stage",
    ),
    "DATASET_PRINCIPAL_ID": (
        "dataset-agent",
        "Principal for public dataset discovery stage",
    ),
    "SCHEMA_PRINCIPAL_ID": (
        "schema-agent",
        "Principal for dataset schema inspection stage",
    ),
    "ANALYSIS_PRINCIPAL_ID": (
        "analysis-agent",
        "Principal for executable analysis design stage",
    ),
    "FINAL_PROPOSAL_PRINCIPAL_ID": (
        "final-proposal-agent",
        "Principal for final proposal assembly stage",
    ),
    "PAPER_PLANNER_PRINCIPAL_ID": (
        "paper-planner-agent",
        "Principal for paper planner stage",
    ),
    "PAPER_INTRO_PRINCIPAL_ID": (
        "paper-intro-agent",
        "Principal for introduction and abstract writing stage",
    ),
    "PAPER_LITREVIEW_PRINCIPAL_ID": (
        "paper-litreview-agent",
        "Principal for literature review writing stage",
    ),
    "PAPER_METHODOLOGY_PRINCIPAL_ID": (
        "paper-methodology-agent",
        "Principal for methodology writing stage",
    ),
    "PAPER_RESULTS_PRINCIPAL_ID": (
        "paper-results-agent",
        "Principal for results and discussion writing stage",
    ),
    "PAPER_CONCLUSION_PRINCIPAL_ID": (
        "paper-conclusion-agent",
        "Principal for conclusion writing stage",
    ),
    "PAPER_FINALIZATION_PRINCIPAL_ID": (
        "paper-finalization-agent",
        "Principal for paper assembly and finalization stage",
    ),
    "PAPER_REVIEW_PRINCIPAL_ID": (
        "paper-review-agent",
        "Principal for paper review and polish stage",
    ),
    "REPO_GRADER_PRINCIPAL_ID": (
        "repo-grader-agent",
        "Principal for repository grading stage",
    ),
    "REPO_SELECTOR_PRINCIPAL_ID": (
        "repo-selector-agent",
        "Principal for repository selection stage",
    ),

}


def create_principal(name: str, description: str) -> str:
    if not BASE_URL:
        raise RuntimeError("BASE_URL is missing. Add it to .env first.")
    if not API_KEY:
        raise RuntimeError("API_KEY is missing. Add it to .env first.")

    url = f"{BASE_URL.rstrip('/')}/api/principal/create"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    body = {
        "principalName": name,
        "principalDescription": description,
    }

    response = requests.post(url, headers=headers, json=body, timeout=60)
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data") or {}
    principal_id = (
        data.get("principalId")
        or data.get("principalID")
        or data.get("id")
        or payload.get("principalId")
    )

    if not principal_id:
        raise RuntimeError(
            "Principal was created, but the response did not include a principal ID.\n"
            f"Response body:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
        )

    return str(principal_id)


def main() -> None:
    created: dict[str, str] = {}

    for env_name, (principal_name, description) in PRINCIPALS.items():
        print(f"Creating {principal_name}...")
        created[env_name] = create_principal(principal_name, description)

    print("\nAdd these lines to your .env file:\n")
    for env_name, principal_id in created.items():
        print(f"{env_name}={principal_id}")


if __name__ == "__main__":
    main()
