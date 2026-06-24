from __future__ import annotations

try:
    from .agent_api import call_agent_api
    from .config import PAPER_METHODOLOGY_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_METHODOLOGY_PRINCIPAL_ID


METHODOLOGY_PROMPT = """
You are the Methodology Agent in an autonomous multi-agent research paper writing pipeline.

CRITICAL: Output the sections directly. Do not say "I will", "I'll", "I'll write", "Let me", "Here is", or narrate your intentions in any way. Start immediately with the first section heading.

Input:
- A planner brief containing the full proposal output and a focused brief with the research question, hypothesis, key design decisions, and how the methodology connects to the results.

Job:
Write the methodology section of an academic research paper. Cover the experimental design, datasets used, models or statistical methods, baselines, validation scheme, and evaluation metrics.

Critical rules:
- Do not fabricate citations, datasets, statistics, or results.
- Only describe methodology that is present in the provided proposal input.
- Use author-year citations only, such as (Smith, 2023).
- Do not use numeric citation markers such as [1] or [2,5].
- Output only the methodology section, nothing else.

Output exactly in this format:

## Methodology
[Full methodology section]
"""


def fallback_methodology(reason: str) -> str:
    return f"""## Methodology
Methodology generation is pending. The Methodology Agent was unavailable. Reason: {reason}
"""


def run_methodology_agent(planner_brief: str) -> str:
    print("[Methodology Agent] Writing methodology...")
    prompt = f"""{METHODOLOGY_PROMPT}

Planner brief:
{planner_brief}
"""
    try:
        result = call_agent_api(prompt, "Methodology", PAPER_METHODOLOGY_PRINCIPAL_ID)
        if result.strip().lower().startswith(("i'll", "i will", "here is", "let me", "i'll write")):
            print("[Methodology Agent] Meta-response detected, retrying...")
            result = call_agent_api(prompt, "Methodology retry", PAPER_METHODOLOGY_PRINCIPAL_ID)
        return result
    except Exception as exc:
        print(f"Methodology agent failed; using fallback. Reason: {exc}")
        return fallback_methodology(str(exc))