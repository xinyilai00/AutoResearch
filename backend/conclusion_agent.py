from __future__ import annotations

try:
    from .agent_api import call_agent_api
    from .config import PAPER_CONCLUSION_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_CONCLUSION_PRINCIPAL_ID


CONCLUSION_PROMPT = """
You are the Conclusion Agent in an autonomous multi-agent research paper writing pipeline.

CRITICAL: Output the complete assembled paper directly. Do not say "I will", "I'll", "Let me", "Here is", or narrate your intentions in any way. Start immediately with the paper title as a Markdown H1 heading.
Input:
- A planner brief containing the full proposal output, full experiment output, and a focused brief with the research question, hypothesis result, key findings, contributions, limitations, and suggested future work.

Job:
Write the conclusion section of an academic research paper. Restate the research question, summarize key findings, state whether the hypothesis was supported, discuss limitations, and suggest future work directions.

Critical rules:
- Do not fabricate citations, datasets, statistics, or results.
- Only report findings that are present in the provided inputs.
- If experiment output is missing or marked REDESIGN_NEEDED, state clearly that conclusions are provisional.
- Use author-year citations only, such as (Smith, 2023).
- Do not use numeric citation markers such as [1] or [2,5].
- Output only the conclusion section, nothing else.

Output exactly in this format:

## Conclusion
[Full conclusion section]
"""


def fallback_conclusion(reason: str) -> str:
    return f"""## Conclusion
Conclusion generation is pending. The Conclusion Agent was unavailable. Reason: {reason}
"""


def run_conclusion_agent(planner_brief: str) -> str:
    print("[Conclusion Agent] Writing conclusion...")
    prompt = f"""{CONCLUSION_PROMPT}

Planner brief:
{planner_brief}
"""
    try:
        result = call_agent_api(prompt, "Conclusion", PAPER_CONCLUSION_PRINCIPAL_ID)
        if result.strip().lower().startswith(("i'll", "i will", "here is", "let me", "i'll write")):
            print("[Conclusion Agent] Meta-response detected, retrying...")
            result = call_agent_api(prompt, "Conclusion retry", PAPER_CONCLUSION_PRINCIPAL_ID)
        return result
    except Exception as exc:
        print(f"Conclusion agent failed; using fallback. Reason: {exc}")
        return fallback_conclusion(str(exc))