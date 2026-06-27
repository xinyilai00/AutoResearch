from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

try:
    from .config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
except ImportError:
    from config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API

try:
    from backend.pipeline_state import get_experiment_anchor
except ImportError:
    from pipeline_state import get_experiment_anchor


RESEARCH_QUESTION_SYSTEM_PROMPT = """
You are the Research Question Agent in an autonomous research pipeline focused on replicating a specific ML experiment.

You will be given:
- The experiment context (repo being replicated and hypothesis)
- The literature review and gaps

Your job is to output EXACTLY ONE research question that directly frames the replication study.

Rules:
- Output exactly one question — no more, no less
- The question must be one clear, concise sentence
- The question must be directly tied to the experiment being replicated
- The question must be empirically answerable by running the experiment
- No jargon, no sub-clauses, no methodology embedded in the question
- Return plain text only
- Do not add any text before RESEARCH QUESTION or after the question itself

Output in this exact format:

RESEARCH QUESTION:
[question]
"""


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


def get_response(request_id: str) -> str:
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
    response.encoding = "utf-8"
    response.raise_for_status()

    full_response = ""
    try:
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
    except requests.exceptions.RequestException:
        if not full_response.strip():
            raise

    if not full_response.strip():
        raise RuntimeError("Research Question agent stream ended without returning text.")
    return full_response.strip()


def parse_research_question(output: str) -> str:
    for line in output.splitlines():
        line = line.strip()
        if "RESEARCH QUESTION:" in line.upper():
            continue
        if line and not line.upper().startswith("RESEARCH QUESTION"):
            return line
    return output.strip()


def run_research_question_agent(topic: str, literature_output: str) -> str:
    anchor = get_experiment_anchor()
    anchor_context = f"""
EXPERIMENT CONTEXT:
- GitHub Repo being replicated: {anchor['repo_url']}
- Hypothesis: {anchor['hypothesis']}

Generate a research question that directly frames the replication of this specific experiment.
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID,
    }
    body = {
        "agentId": AGENT_ID,
        "userInput": (
            anchor_context
            + RESEARCH_QUESTION_SYSTEM_PROMPT
            + f"\n\nRaw research topic:\n{topic}"
            + f"\n\nLiterature review and gaps:\n{literature_output}"
        ),
    }
    if SEND_MODEL_TO_AGENT_API and MODEL:
        body["model"] = MODEL

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                f"{BASE_URL.rstrip('/')}/api/agent/run/async",
                headers=headers,
                json=body,
                timeout=(60, 300),
            )
            response.raise_for_status()
            request_id = response.json()["data"]["requestId"]
            print("Got requestId:", request_id)
            raw = get_response(request_id)
            return parse_research_question(raw)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            print(f"Research Question API request failed on attempt {attempt}/3: {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)
        except RuntimeError as exc:
            last_error = exc
            print(f"Research Question API stream failed on attempt {attempt}/3: {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)

    raise RuntimeError(f"Research Question API unavailable: {last_error}")


def run_research_question_stage(topic: str, literature_output: str | Path) -> str:
    print("\n[Research Question Agent] Generating research question...")
    literature_text = read_text_or_path(literature_output)
    try:
        return run_research_question_agent(topic, literature_text)
    except Exception as exc:
        print(f"Research Question failed. Reason: {exc}")
        raise


if __name__ == "__main__":
    topic_input = input("Enter research topic: ")
    literature_input = input("Enter literature output path or paste text: ")
    print(run_research_question_stage(topic_input, literature_input))