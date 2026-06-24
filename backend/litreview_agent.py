from __future__ import annotations

try:
    from .agent_api import call_agent_api
    from .config import PAPER_LITREVIEW_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_LITREVIEW_PRINCIPAL_ID


LITREVIEW_PROMPT = """
You are the Literature Review Agent in an autonomous multi-agent research paper writing pipeline.

Input:
- A planner brief containing the full deep literature review and a focused brief with the angle, key themes, research gap, and tone.

Job:
Write the literature review section of an academic research paper. Synthesize prior work into a cohesive narrative that builds toward the research gap the paper addresses.

Critical rules:
- Do not fabricate citations, datasets, statistics, or results.
- Only cite works that appear in the provided literature review input.
- Use author-year citations only, such as (Smith, 2023).
- Do not use numeric citation markers such as [1] or [2,5].
- Output only the literature review section, nothing else.

Output exactly in this format:

## Literature Review
[Full literature review section]
"""


def fallback_litreview(reason: str) -> str:
    return f"""## Literature Review
Literature review generation is pending. The Literature Review Agent was unavailable. Reason: {reason}
"""


def run_litreview_agent(planner_brief: str) -> str:
    print("[Lit Review Agent] Writing literature review...")
    prompt = f"""{LITREVIEW_PROMPT}

Planner brief:
{planner_brief}
"""
    try:
        return call_agent_api(prompt, "Lit Review", PAPER_LITREVIEW_PRINCIPAL_ID)
    except Exception as exc:
        print(f"Lit Review agent failed; using fallback. Reason: {exc}")
        return fallback_litreview(str(exc))