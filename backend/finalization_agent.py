from __future__ import annotations


try:
   from .agent_api import call_agent_api
   from .config import PAPER_INTRO_PRINCIPAL_ID
except ImportError:
   from agent_api import call_agent_api
   from config import PAPER_INTRO_PRINCIPAL_ID




FINALIZATION_PROMPT = """
You are starting a completely fresh task. Ignore any previous context or conversations.


You are the Paper Assembly Agent in an autonomous multi-agent research paper writing pipeline.


CRITICAL:
- Output the complete assembled paper directly as plain text in this response.
- Do NOT write to any files.
- Do NOT use any tools.
- Do NOT summarize what you did.
- Do NOT say "the paper has been delivered" or "here is a summary".
- Do NOT include any text before the paper title.
- Start immediately with the paper title as a Markdown H1 heading.
- Your entire response must be the full paper text itself.


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
   meta_starts = (
       "i'll", "i will", "here is", "let me", "the complete",
       "the paper has", "i have assembled", "below is",
       "i've assembled", "the assembled", "here's the",
       "the complete assembled", "all seven sections",
   )
   try:
       result = call_agent_api(prompt, "Finalization", PAPER_INTRO_PRINCIPAL_ID)
       if result.strip().lower().startswith(meta_starts):
           print("[Finalization Agent] Meta-response detected, retrying...")
           result = call_agent_api(prompt, "Finalization retry", PAPER_INTRO_PRINCIPAL_ID)
       if result.strip().lower().startswith(meta_starts):
           print("[Finalization Agent] Meta-response on retry, using fallback.")
           return fallback_finalization(intro, litreview, methodology, results, conclusion, "Meta-response detected twice.")
       return result
   except Exception as exc:
       print(f"Finalization agent failed; using fallback. Reason: {exc}")
       return fallback_finalization(intro, litreview, methodology, results, conclusion, str(exc))

