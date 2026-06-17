from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from config import AGENT_ID, API_KEY, BASE_URL, PRINCIPAL_ID


REVIEW_SYSTEM_PROMPT = """
You are the Review agent in an autonomous research pipeline.

Input: a draft academic paper.

Job:
- Revise the paper for clarity, evidence discipline, and academic structure.
- Cross-check statistics in the paper against claims.
- Identify unsupported claims, weak experiments, missing baselines, citation
  problems, fabricated-looking references, result/interpretation leakage, and
  visual provenance issues.
- Preserve truthful uncertainty. Do not fabricate citations, datasets,
  statistics, experiments, or results.

Output:
1. A revised draft of the paper.
2. A weakness report listing unsupported claims, weak experiments, citation
   issues, statistical inconsistencies, and remaining limitations.

Return your answer in Markdown with exactly these top-level headings:
# Revised Draft
# Identified Weaknesses
"""


@dataclass
class ReviewResult:
    revised_draft: str
    weaknesses: str
    raw: str


def run_agent_prompt(user_input: str) -> str:
    import requests

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID,
    }
    body = {
        "agentId": AGENT_ID,
        "userInput": user_input,
    }
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                f"{BASE_URL.rstrip('/')}/api/agent/run/async",
                headers=headers,
                json=body,
                timeout=180,
            )
            response.raise_for_status()
            request_id = response.json()["data"]["requestId"]
            return read_agent_stream(request_id)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            print(f"Review API request failed on attempt {attempt}/3: {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)
        except RuntimeError as exc:
            last_error = exc
            print(f"Review API stream failed on attempt {attempt}/3: {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)

    return fallback_review_output(str(last_error))


def read_agent_stream(request_id: str) -> str:
    import requests

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID,
    }
    response = requests.get(
        f"{BASE_URL.rstrip('/')}/api/agent/run/stream",
        headers=headers,
        params={"requestId": request_id},
        stream=True,
        timeout=(30, 300),
    )
    response.raise_for_status()

    full_response = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            data = json.loads(line[5:])
        except json.JSONDecodeError:
            continue

        event_type = data.get("eventType")
        if event_type in {"TEXT_START", "TEXT_DELTA"}:
            full_response += data.get("data", {}).get("text", "")
        if event_type in {"TEXT_END", "MESSAGE_COMPLETED", "RUN_COMPLETED", "DONE", "COMPLETED"}:
            if full_response.strip():
                break

    if not full_response.strip():
        raise RuntimeError("Review agent stream ended without returning text.")
    return full_response.strip()


def split_review_output(raw: str) -> ReviewResult:
    revised_match = re.search(
        r"# Revised Draft\s*(.*?)(?=\n# Identified Weaknesses|\Z)",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    weakness_match = re.search(
        r"# Identified Weaknesses\s*(.*)\Z",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )

    revised = revised_match.group(1).strip() if revised_match else raw.strip()
    weaknesses = weakness_match.group(1).strip() if weakness_match else "No separate weakness report was returned."
    return ReviewResult(revised_draft=revised, weaknesses=weaknesses, raw=raw)


def fallback_review_output(reason: str) -> str:
    return f"""# Revised Draft

Review agent could not reach the API, so no API-generated revision was produced.
Use the original paper draft as the current reviewed draft until the API is
reachable again.

# Identified Weaknesses

- Review API unavailable: {reason}
- Citation verification could not be performed.
- Statistical claim checking could not be performed.
- Experiment strength could not be evaluated.
- Re-run review_agent.py when the API endpoint is reachable.
"""


def run_review_agent(draft: str, output_dir: str | Path | None = None) -> ReviewResult:
    prompt = f"""{REVIEW_SYSTEM_PROMPT}

Draft paper:
{draft}
"""
    raw = run_agent_prompt(prompt)
    result = split_review_output(raw)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "reviewed_draft.md").write_text(result.revised_draft.rstrip() + "\n", encoding="utf-8")
        (out / "identified_weaknesses.md").write_text(result.weaknesses.rstrip() + "\n", encoding="utf-8")
        (out / "review_agent_raw.md").write_text(result.raw.rstrip() + "\n", encoding="utf-8")

    return result


def run_review_from_file(draft_path: str | Path, output_dir: str | Path | None = None) -> ReviewResult:
    draft = Path(draft_path).read_text(encoding="utf-8")
    return run_review_agent(draft, output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review and revise a generated research paper draft.")
    parser.add_argument("--draft", default="paper_runs/latest/final.md", help="Draft paper Markdown file.")
    parser.add_argument("--out", default="paper_runs/latest/review", help="Review output directory.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_review_from_file(args.draft, args.out)
    print(f"Reviewed draft: {Path(args.out) / 'reviewed_draft.md'}")
    print(f"Weaknesses: {Path(args.out) / 'identified_weaknesses.md'}")
