from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from config import AGENT_ID, API_KEY, BASE_URL, PRINCIPAL_ID


@dataclass
class ReviewScore:
    novelty: int
    correctness: int
    evidence: int
    clarity: int
    reproducibility: int

    @property
    def total(self) -> int:
        return self.novelty + self.correctness + self.evidence + self.clarity + self.reproducibility


@dataclass
class Review:
    score: ReviewScore
    strengths: list[str]
    weaknesses: list[str]
    revision_plan: list[str]


def run_agent_prompt(user_input: str) -> str:
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

    raise RuntimeError(f"Review API unavailable: {last_error}")


def read_agent_stream(request_id: str) -> str:
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

    full = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            data = json.loads(line[5:])
        except json.JSONDecodeError:
            continue

        event_type = data.get("eventType")
        if event_type in {"TEXT_START", "TEXT_DELTA"}:
            full += data.get("data", {}).get("text", "")
        if event_type in {"TEXT_END", "MESSAGE_COMPLETED", "RUN_COMPLETED", "DONE", "COMPLETED"}:
            if full.strip():
                break

    if not full.strip():
        raise RuntimeError("Review agent stream ended without returning text.")
    return full.strip()


def parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in review output.")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])

    raise ValueError("Could not parse JSON object from review output.")


def clamp_score(value: object) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(5, score))


def list_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def review_draft(draft: str) -> Review:
    prompt = f"""Review this research paper draft.

Return ONLY valid JSON with this exact schema:
{{
  "novelty": 1-5,
  "correctness": 1-5,
  "evidence": 1-5,
  "clarity": 1-5,
  "reproducibility": 1-5,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "revision_plan": ["..."]
}}

Check specifically for:
- unsupported claims
- weak experiments
- citation issues
- statistical claims not supported by results
- fabricated-looking references
- unclear methodology
- missing limitations
- result/discussion leakage
- visual provenance problems

Draft:
{draft}
"""
    raw = run_agent_prompt(prompt)
    try:
        data = parse_json_object(raw)
    except Exception as exc:
        print(f"Review JSON parse failed; using fallback review. Reason: {exc}")
        data = {
            "novelty": 2,
            "correctness": 2,
            "evidence": 1,
            "clarity": 2,
            "reproducibility": 1,
            "strengths": ["The draft exists and has a paper-like structure."],
            "weaknesses": ["The review model did not return valid JSON."],
            "revision_plan": ["Re-run review or manually inspect unsupported claims."],
        }

    score = ReviewScore(
        novelty=clamp_score(data.get("novelty")),
        correctness=clamp_score(data.get("correctness")),
        evidence=clamp_score(data.get("evidence")),
        clarity=clamp_score(data.get("clarity")),
        reproducibility=clamp_score(data.get("reproducibility")),
    )
    return Review(
        score=score,
        strengths=list_strings(data.get("strengths")),
        weaknesses=list_strings(data.get("weaknesses")),
        revision_plan=list_strings(data.get("revision_plan")),
    )


def revise_draft(draft: str, review: Review) -> str:
    prompt = f"""Revise this paper using the review.

Rules:
- Output the complete revised paper, not a diff.
- Fix as many weaknesses as possible.
- Preserve truthful uncertainty.
- Do not fabricate citations, datasets, statistics, or results.
- If experiments are weak or missing, state that clearly.
- If citations are unverified, mark them TODO.
- Keep the required paper sections.

Review:
{json.dumps(asdict(review), indent=2)}

Draft:
{draft}
"""
    return run_agent_prompt(prompt)


def format_review(review: Review) -> str:
    return "\n".join(
        [
            "# Review",
            "",
            "## Scores",
            f"- Novelty: {review.score.novelty}/5",
            f"- Correctness: {review.score.correctness}/5",
            f"- Evidence: {review.score.evidence}/5",
            f"- Clarity: {review.score.clarity}/5",
            f"- Reproducibility: {review.score.reproducibility}/5",
            f"- Total: {review.score.total}/25",
            "",
            "## Strengths",
            *format_bullets(review.strengths),
            "",
            "## Weaknesses",
            *format_bullets(review.weaknesses),
            "",
            "## Revision Plan",
            *format_bullets(review.revision_plan),
        ]
    )


def format_bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- None provided."]


def fallback_review_output(output_dir: Path, draft: str, reason: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reviewed_draft.md").write_text(draft.rstrip() + "\n", encoding="utf-8")
    (output_dir / "remaining_weaknesses.md").write_text(
        "\n".join(
            [
                "# Review",
                "",
                "## Weaknesses",
                f"- Review API unavailable: {reason}",
                "- Citation verification could not be performed.",
                "- Statistical claim checking could not be performed.",
                "- Experiment strength could not be evaluated.",
                "- Re-run review_agent.py when the API endpoint is reachable.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "review_summary.json").write_text(
        json.dumps({"error": reason, "fallback": True}, indent=2),
        encoding="utf-8",
    )
    return output_dir


def run_review_agent(draft: str, output_dir: str | Path = "paper_runs/latest/review", rounds: int = 2) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    current_draft = draft

    try:
        for round_number in range(1, rounds + 1):
            print(f"Review round {round_number}...")
            review = review_draft(current_draft)
            (output_path / f"review_round_{round_number:02d}.md").write_text(
                format_review(review),
                encoding="utf-8",
            )

            print(f"Revising draft round {round_number}...")
            current_draft = revise_draft(current_draft, review)
            (output_path / f"revised_round_{round_number:02d}.md").write_text(
                current_draft.rstrip() + "\n",
                encoding="utf-8",
            )

        print("Final review after revisions...")
        final_review = review_draft(current_draft)
    except Exception as exc:
        return fallback_review_output(output_path, current_draft, str(exc))

    (output_path / "reviewed_draft.md").write_text(current_draft.rstrip() + "\n", encoding="utf-8")
    (output_path / "remaining_weaknesses.md").write_text(format_review(final_review), encoding="utf-8")
    (output_path / "review_summary.json").write_text(
        json.dumps(
            {
                "final_score": asdict(final_review.score),
                "final_total": final_review.score.total,
                "strengths": final_review.strengths,
                "remaining_weaknesses": final_review.weaknesses,
                "revision_plan": final_review.revision_plan,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path


def run_review_from_file(draft_path: str | Path, output_dir: str | Path | None = None, rounds: int = 2) -> Path:
    draft = Path(draft_path).read_text(encoding="utf-8")
    return run_review_agent(draft, output_dir or "paper_runs/latest/review", rounds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review and revise a paper draft.")
    parser.add_argument("--draft", default="paper_runs/latest/final.md")
    parser.add_argument("--out", default="paper_runs/latest/review")
    parser.add_argument("--rounds", type=int, default=2)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    out = run_review_from_file(args.draft, args.out, args.rounds)
    print(f"Reviewed draft: {out / 'reviewed_draft.md'}")
    print(f"Remaining weaknesses: {out / 'remaining_weaknesses.md'}")
