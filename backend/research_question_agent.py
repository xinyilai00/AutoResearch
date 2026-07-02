from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

try:
    from .config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API, JSON_AGENT_ID
    from .agent_api import call_agent_api_json
except ImportError:
    from config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API, JSON_AGENT_ID
    from agent_api import call_agent_api_json


RESEARCH_QUESTION_SYSTEM_PROMPT = """
You are the Research Question Agent in an autonomous research pipeline.

You will be given a research topic and a literature review.

Your job is to generate 5 to 10 candidate research questions based on the literature review and identified gaps.

CRITICAL PIPELINE CONSTRAINTS — every question MUST satisfy ALL of these:
- The question must be answerable by cloning a public GitHub repository, running a Python script on a standard CPU laptop, and measuring numerical output (accuracy, loss, perplexity, F1, speed, etc.)
- The experiment must be completable in under 15 minutes on CPU with no GPU
- No physical hardware required (no robots, no mobile devices, no IoT sensors, no cameras)
- No human subjects, user studies, surveys, or subjective evaluation
- No proprietary, paid, or institutional datasets — only publicly available data
- No questions about energy consumption, power draw, or hardware-level metrics that require specialized measurement tools
- No questions that are purely theoretical or require only mathematical proof
- The question must have a clear independent variable that can be controlled in code (e.g. compression ratio, model size, number of layers, training data size)
- The question must have a clear measurable dependent variable that appears as a number in stdout

Rules for question quality:
- Each question must be one clear, concise, plain-English sentence
- Each question must be understandable to a non-expert
- Questions should vary in angle and focus — do not just rephrase the same question
- No jargon, no sub-clauses, no methodology embedded in the question
- Return a JSON array of strings only, no explanation, no preamble

Example of a GOOD question: "Does increasing the number of attention heads in a transformer improve text classification accuracy?"
Example of a BAD question: "How does pruning affect inference latency on mobile hardware?" (requires mobile hardware)
Example of a BAD question: "Do users prefer compressed models?" (requires human subjects)
Example of a BAD question: "Does quantization reduce energy consumption?" (requires power measurement tools)
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


def run_research_question_agent(topic: str, literature_output: str) -> str:
    prompt = (
        RESEARCH_QUESTION_SYSTEM_PROMPT
        + f"\n\nResearch topic:\n{topic}"
        + f"\n\nLiterature review and gaps:\n{literature_output}"
    )
    result = call_agent_api_json(prompt, "Research Question")
    if isinstance(result, list) and result:
        return json.dumps(result)
    raise RuntimeError(f"Research Question agent did not return a valid list. Got: {result}")


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
