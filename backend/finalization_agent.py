from __future__ import annotations

try:
    from .agent_api import call_agent_api
    from .config import PAPER_FINALIZATION_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_FINALIZATION_PRINCIPAL_ID


FINALIZATION_PROMPT = """
You are the Finalization Agent in an autonomous multi-agent research paper writing pipeline.

Input:
- Five independently written paper sections: Abstract, Introduction, Literature Review, Methodology, Results, Discussion, Conclusion.
- The planner output for reference on overall narrative and contributions.

Job:
Assemble the sections into a complete, polished academic research paper. Your tasks are:
1. Assemble all sections in the correct order.
2. Insert and format citations consistently throughout — convert any remaining numeric markers like [1] or [2,5] to author-year format.
3. Add a References section at the end listing all cited works in author-year format.
4. Light polish for consistent voice, tense, and terminology throughout.
5. Ensure section headings are consistent and properly formatted.

Critical rules:
- Do not fabricate citations, datasets, statistics, or results.
- Do not rewrite or substantially change the content of any section.
- Do not add new claims or findings not present in the input sections.
- Use author-year citations only, such as (Smith, 2023).
- Do not use numeric citation markers such as [1] or [2,5].
- Output only the complete assembled paper, nothing else.
- Start directly with the paper title as a Markdown H1 heading.

Output format:

# [Paper Title]

## Abstract
...

## Introduction
...

## Literature Review
...

## Methodology
...

## Results
...

## Discussion
...

## Conclusion
...

## References
...
"""


def fallback_finalization(
    intro: str,
    litreview: str,
    methodology: str,
    results: str,
    conclusion: str,
    reason: str,
) -> str:
    return f"""# Research Paper (Unpolished Assembly)

{intro}

{litreview}

{methodology}

{results}

{conclusion}

## References
References pending. Finalization Agent was unavailable. Reason: {reason}
"""


def run_finalization_agent(
    planner_output: dict[str, str],
    intro: str,
    litreview: str,
    methodology: str,
    results: str,
    conclusion: str,
) -> str:
    print("[Finalization Agent] Assembling and polishing paper...")
    prompt = f"""{FINALIZATION_PROMPT}

Planner output (for narrative reference):
{planner_output.get("intro", "")}

Sections to assemble:

{intro}

{litreview}

{methodology}

{results}

{conclusion}
"""
    try:
        return call_agent_api(prompt, "Finalization", PAPER_FINALIZATION_PRINCIPAL_ID)
    except Exception as exc:
        print(f"Finalization agent failed; using fallback. Reason: {exc}")
        return fallback_finalization(intro, litreview, methodology, results, conclusion, str(exc))