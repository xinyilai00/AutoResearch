from __future__ import annotations

try:
    from .agent_api import call_agent_api
    from .config import PAPER_RESULTS_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_RESULTS_PRINCIPAL_ID


RESULTS_PROMPT = """
You are the Results and Discussion Agent in an autonomous multi-agent research paper writing pipeline.

CRITICAL: Output the sections directly. Do not say "I will", "I'll", "I'll write", "Let me", "Here is", or narrate your intentions in any way. Start immediately with the first section heading.

Input:
- A planner brief containing the full experiment output and a focused brief with the hypothesis result, key metrics, limitations, and how results connect to the research question and literature.

Job:
Write two sections of an academic research paper:
1. Results: present the experiment findings clearly and objectively. Include metrics, comparisons to baselines, and statistical significance where available.
2. Discussion: interpret the results, explain what they mean in the context of the research question and prior literature, discuss limitations and threats to validity.

Critical rules:
- Do not fabricate citations, datasets, statistics, or results.
- Only report findings that are present in the provided experiment output.
- If experiment output is missing or marked REDESIGN_NEEDED, state clearly that results are pending.
- Use author-year citations only, such as (Smith, 2023).
- Do not use numeric citation markers such as [1] or [2,5].
- Output only the two sections, nothing else.

Output exactly in this format:

## Results
[Full results section]

## Discussion
[Full discussion section]
"""


def fallback_results(reason: str) -> str:
    return f"""## Results
Results generation is pending. The Results and Discussion Agent was unavailable. Reason: {reason}

## Discussion
Discussion generation is pending. The Results and Discussion Agent was unavailable. Reason: {reason}
"""


def run_results_agent(planner_brief: str) -> str:
    print("[Results Agent] Writing results and discussion...")
    prompt = f"""{RESULTS_PROMPT}

Planner brief:
{planner_brief}
"""
    try:
        result = call_agent_api(prompt, "Results", PAPER_RESULTS_PRINCIPAL_ID)
        if result.strip().lower().startswith(("i'll", "i will", "here is", "let me", "i'll write")):
            print("[Results Agent] Meta-response detected, retrying...")
            result = call_agent_api(prompt, "Results retry", PAPER_RESULTS_PRINCIPAL_ID)
        return result
    except Exception as exc:
        print(f"Results agent failed; using fallback. Reason: {exc}")
        return fallback_results(str(exc))