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


RESEARCH_QUESTION_SYSTEM_PROMPT = """
You are the Research Question Agent in an autonomous research pipeline.

Input:
- Raw research topic
- Part 1 literature review containing existing work and gaps

Job:
Generate 5-10 candidate research questions that fill gaps identified in the literature.

Rules:
- Each question must be one clear, concise sentence.
- Each question must be understandable to an intelligent non-expert — no jargon, no sub-clauses, no embedded methodology.
- Each question must be specific and empirically answerable.
- Each question must be feasible for an AI research pipeline to investigate autonomously using computational methods, public datasets, public repositories, database records, simulations, or synthetically generated data.
- Do NOT propose questions requiring physical experiments, lab equipment, human subjects, private/proprietary data, or impossible data collection.
- Do NOT fabricate citations, datasets, or prior findings.
- Do NOT use numeric citation markers such as [1], [22], [2,5], or [3-6].
- Do NOT include gap analysis, feasibility notes, or any metadata alongside the question — just the question itself.
- Rank questions from most to least promising.
- Return plain text only.
- Do not add text before CANDIDATE RESEARCH QUESTIONS or after the final question.

Output in this exact format:

CANDIDATE RESEARCH QUESTIONS:
1. [question]
2. [question]
...
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


def run_research_question_agent(topic: str, literature_output: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID,
    }
    body = {
        "agentId": AGENT_ID,
        "userInput": (
            RESEARCH_QUESTION_SYSTEM_PROMPT
            + f"\n\nRaw research topic:\n{topic}"
            + f"\n\nPart 1 literature review and gaps:\n{literature_output}"
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
            return get_response(request_id)
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


def parse_candidate_research_questions(question_output: str) -> list[str]:
    questions = []
    in_questions_section = False

    for line in question_output.splitlines():
        line = line.strip()

        if "CANDIDATE RESEARCH QUESTIONS" in line.upper():
            in_questions_section = True
            continue

        if in_questions_section and line and line[0].isdigit() and (". " in line or ") " in line):
            if ". " in line:
                question = line.split(". ", 1)[1].strip()
            else:
                question = line.split(") ", 1)[1].strip()
            if "| Gap addressed:" in question:
                question = question.split("| Gap addressed:", 1)[0].strip()
            if "| Feasibility:" in question:
                question = question.split("| Feasibility:", 1)[0].strip()
            if len(question) > 30:
                questions.append(question)

    return questions


def fallback_research_questions(topic: str, reason: str) -> str:
    return f"""CANDIDATE RESEARCH QUESTIONS:
1. What computationally testable research question can be derived from the topic "{topic}" once literature gaps are verified? | Gap addressed: TO_VERIFY | Feasibility: Pending because the Research Question Agent failed: {reason}
"""


def run_research_question_stage(topic: str, literature_output: str | Path) -> str:
    print("\n[Research Question Agent] Generating candidate questions...")
    literature_text = read_text_or_path(literature_output)
    try:
        return run_research_question_agent(topic, literature_text)
    except Exception as exc:
        print(f"Research Question failed; using placeholder. Reason: {exc}")
        return fallback_research_questions(topic, str(exc))


if __name__ == "__main__":
    topic_input = input("Enter research topic: ")
    literature_input = input("Enter literature output path or paste text: ")
    print(run_research_question_stage(topic_input, literature_input))
