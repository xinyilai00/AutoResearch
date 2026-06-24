from __future__ import annotations

from pathlib import Path

try:
    from .agent_api import call_agent_api
    from .config import PAPER_PLANNER_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_PLANNER_PRINCIPAL_ID


PLANNER_PROMPT = """
You are the Planner Agent in an autonomous multi-agent research paper writing pipeline.

Input:
- Research topic
- PI output
- Literature review part 1 (broad literature)
- Literature review part 2 (deep literature)
- Selected research question
- Proposal output
- Experiment output

Job:
Read all stage inputs carefully and produce five tailored packages, one for each inner writing agent.
Each package contains:
1. The full relevant raw stage output(s) for that agent
2. A focused brief with angle, emphasis, key findings, hypothesis result, contributions, and how it fits the paper's overall narrative

Critical rules:
- Do not write any section of the paper yourself.
- Do not fabricate citations, datasets, statistics, or results.
- If experiment output is missing or marked REDESIGN_NEEDED, note this clearly in all relevant briefs.
- Use author-year citations only, such as (Smith, 2023).
- Be specific and directive in each brief — the inner agents rely entirely on your output.

Output exactly in this format:

=== INTRO BRIEF ===
[Full lit p1 output]

BRIEF:
- Core hypothesis: [...]
- Key findings and whether hypothesis was supported: [...]
- Main contributions of the paper: [...]
- Research gap being addressed: [...]
- Overall narrative arc: [...]

=== LITREVIEW BRIEF ===
[Full lit p2 output]

BRIEF:
- Angle to take: [...]
- Key themes and concepts to emphasize: [...]
- Gap in literature the paper addresses: [...]
- Tone and framing: [...]

=== METHODOLOGY BRIEF ===
[Full proposal output]

BRIEF:
- Research question being addressed: [...]
- Hypothesis being tested: [...]
- Key decisions to highlight: [...]
- How methodology connects to results: [...]

=== RESULTS BRIEF ===
[Full experiment output]

BRIEF:
- Hypothesis and whether it was supported: [...]
- Key metrics to highlight: [...]
- Limitations to address: [...]
- How results connect to research question and literature: [...]

=== CONCLUSION BRIEF ===
[Full proposal output]
[Full experiment output]

BRIEF:
- Research question and hypothesis: [...]
- Whether hypothesis was supported and key findings: [...]
- Main contributions: [...]
- Limitations to acknowledge: [...]
- Suggested future work: [...]
"""


def parse_planner_output(text: str) -> dict[str, str]:
    sections = {
        "intro": "=== INTRO BRIEF ===",
        "litreview": "=== LITREVIEW BRIEF ===",
        "methodology": "=== METHODOLOGY BRIEF ===",
        "results": "=== RESULTS BRIEF ===",
        "conclusion": "=== CONCLUSION BRIEF ===",
    }
    parsed = {}
    keys = list(sections.keys())
    markers = list(sections.values())

    for index, key in enumerate(keys):
        start_marker = markers[index]
        start = text.find(start_marker)
        if start == -1:
            parsed[key] = ""
            continue
        start += len(start_marker)
        end = len(text)
        if index + 1 < len(markers):
            next_start = text.find(markers[index + 1], start)
            if next_start != -1:
                end = next_start
        parsed[key] = text[start:end].strip()

    return parsed


def fallback_planner(topic: str, reason: str) -> dict[str, str]:
    fallback = f"Planner Agent unavailable. Topic: {topic}. Reason: {reason}. Write the section based on available inputs."
    return {
        "intro": fallback,
        "litreview": fallback,
        "methodology": fallback,
        "results": fallback,
        "conclusion": fallback,
    }


def run_planner_agent(
    topic: str,
    pi_output: str,
    lit_p1: str,
    lit_p2: str,
    research_question: str,
    proposal: str,
    experiment: str,
) -> dict[str, str]:
    print("[Planner Agent] Generating tailored briefs for inner agents...")
    prompt = f"""{PLANNER_PROMPT}

Research topic:
{topic}

PI output:
{pi_output}

Literature review part 1:
{lit_p1}

Literature review part 2 (deep literature):
{lit_p2}

Selected research question:
{research_question}

Proposal output:
{proposal}

Experiment output:
{experiment}
"""
    try:
        raw = call_agent_api(prompt, "Planner", PAPER_PLANNER_PRINCIPAL_ID)
        return parse_planner_output(raw)
    except Exception as exc:
        print(f"Planner failed; using fallback. Reason: {exc}")
        return fallback_planner(topic, str(exc))