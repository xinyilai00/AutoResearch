from __future__ import annotations

from pathlib import Path

try:
    from .agent_api import call_agent_api
    from .config import PAPER_PLANNER_PRINCIPAL_ID, JSON_AGENT_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_PLANNER_PRINCIPAL_ID, JSON_AGENT_ID


PLANNER_PROMPT = """
You are the Planner Agent in an autonomous multi-agent research paper writing pipeline.

CRITICAL: Output the five tailored packages directly. Do not say "I will", "I'll", "Let me", "I'll now", or narrate your intentions. Start immediately with === INTRO BRIEF ===.

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
        "intro": ["=== INTRO BRIEF ===", "INTRO BRIEF", "INTRODUCTION BRIEF"],
        "litreview": ["=== LITREVIEW BRIEF ===", "LITREVIEW BRIEF", "LITERATURE REVIEW BRIEF"],
        "methodology": ["=== METHODOLOGY BRIEF ===", "METHODOLOGY BRIEF"],
        "results": ["=== RESULTS BRIEF ===", "RESULTS BRIEF", "RESULTS AND DISCUSSION BRIEF"],
        "conclusion": ["=== CONCLUSION BRIEF ===", "CONCLUSION BRIEF"],
    }

    parsed = {}
    upper_text = text.upper()

    marker_positions = []
    for key, variants in sections.items():
        for variant in variants:
            pos = upper_text.find(variant.upper())
            if pos != -1:
                marker_positions.append((pos, key, variant))
                break

    marker_positions.sort(key=lambda x: x[0])

    for i, (pos, key, variant) in enumerate(marker_positions):
        start = pos + len(variant)
        end = marker_positions[i + 1][0] if i + 1 < len(marker_positions) else len(text)
        parsed[key] = text[start:end].strip()

    for key in sections:
        if key not in parsed:
            parsed[key] = text

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
    meta_starts = (
        "i'll", "i will", "let me", "i'll now", "here is",
        "i'm going to", "i will now", "let me now", "i'll analyze",
        "i'll carefully", "i'll compile",
    )
    try:
        raw = call_agent_api(prompt, "Planner", PAPER_PLANNER_PRINCIPAL_ID, agent_id=JSON_AGENT_ID)
        if raw.strip().lower().startswith(meta_starts):
            print("[Planner Agent] Meta-response detected, retrying...")
            raw = call_agent_api(prompt, "Planner retry", PAPER_PLANNER_PRINCIPAL_ID, agent_id=JSON_AGENT_ID)
        if raw.strip().lower().startswith(meta_starts):
            print("[Planner Agent] Meta-response on retry, using fallback.")
            return fallback_planner(topic, "Meta-response detected twice.")
        return parse_planner_output(raw)
    except Exception as exc:
        print(f"Planner failed; using fallback. Reason: {exc}")
        return fallback_planner(topic, str(exc))