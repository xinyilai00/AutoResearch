from __future__ import annotations

from pathlib import Path

try:
    from .agent_api import call_agent_api
    from .config import PAPER_INTRO_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_INTRO_PRINCIPAL_ID


INTRO_PROMPT = """
You are the Introduction and Abstract Agent in an autonomous multi-agent research paper writing pipeline.

CRITICAL: Output the sections directly. Do not say "I will", "I'll", "I'll write", "Let me", "Here is", or narrate your intentions in any way. Start immediately with the first section heading.

Input:
- A planner brief containing full literature review part 1, the selected research question, and a focused brief with the paper's core hypothesis, key findings, contributions, research gap, and narrative arc.

Job:
Write two sections of an academic research paper:
1. Abstract (150-200 words): a concise summary of the full paper drawn from the planner brief. Cover the research question, methodology, key findings, and contributions.
2. Introduction: hook the reader, provide background, narrow to the specific research gap, state the research question, and present the paper's contributions and findings as a thesis.

Critical rules:
- Do not fabricate citations, datasets, statistics, or results.
- Draw findings and contributions strictly from the planner brief — do not invent them.
- Use author-year citations only, such as (Smith, 2023).
- Do not use numeric citation markers such as [1] or [2,5].
- Output only the two sections, nothing else.

Output exactly in this format:

## Abstract
[150-200 word abstract]

## Introduction
[Full introduction section]
"""


def fallback_intro(reason: str) -> str:
    return f"""## Abstract
Abstract generation is pending. The Introduction and Abstract Agent was unavailable. Reason: {reason}

## Introduction
Introduction generation is pending. The Introduction and Abstract Agent was unavailable. Reason: {reason}
"""


def run_intro_agent(planner_brief: str) -> str:
    print("[Intro Agent] Writing introduction and abstract...")
    prompt = f"""{INTRO_PROMPT}

Planner brief:
{planner_brief}
"""
    try:
        result = call_agent_api(prompt, "Intro", PAPER_INTRO_PRINCIPAL_ID)
        if result.strip().lower().startswith(("i'll", "i will", "here is", "let me", "i'll write")):
            print("[Intro Agent] Meta-response detected, retrying...")
            result = call_agent_api(prompt, "Intro retry", PAPER_INTRO_PRINCIPAL_ID)
        return result
    except Exception as exc:
        print(f"Intro agent failed; using fallback. Reason: {exc}")
        return fallback_intro(str(exc))