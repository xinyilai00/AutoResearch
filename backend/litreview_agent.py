from __future__ import annotations

try:
    from .agent_api import call_agent_api
    from .config import PAPER_LITREVIEW_PRINCIPAL_ID, JSON_AGENT_ID
except ImportError:
    from agent_api import call_agent_api
    from config import PAPER_LITREVIEW_PRINCIPAL_ID, JSON_AGENT_ID


LITREVIEW_PROMPT = """
You are starting a completely fresh task. Ignore any previous context or conversations.

You are the Paper Section Writer (Literature Review) in an autonomous multi-agent research paper writing pipeline.

CRITICAL: 
- Output the literature review section as PLAIN TEXT directly in this response.
- Do NOT write to any files.
- Do NOT use any tools.
- Do NOT save to any workspace or directory.
- Do NOT summarize what you wrote.
- Do NOT say the file has been delivered.
- Your entire response must be the literature review text itself, starting with ## Literature Review.

You will receive raw research notes and source material from upstream research stages. These are NOT a completed paper section — they are reference material only.

Your job is to use this material to write the Literature Review SECTION of an academic research paper. This is different from the upstream literature research that was conducted — you are writing the final paper section that will appear in the published paper.

Start immediately with ## Literature Review and write the full section in academic prose.

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


META_STARTS = (
    "i'll", "i will", "here is", "let me", "i'll write",
    "the literature review has", "i have already", "i've already",
    "the literature review was", "this has already been",
    "the literature review section", "i have written",
)


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
        result = call_agent_api(prompt, "Lit Review", PAPER_LITREVIEW_PRINCIPAL_ID, agent_id=JSON_AGENT_ID)
        if result.strip().lower().startswith(META_STARTS):
            print("[Lit Review Agent] Meta-response detected, retrying...")
            result = call_agent_api(prompt, "Lit Review retry", PAPER_LITREVIEW_PRINCIPAL_ID, agent_id=JSON_AGENT_ID)
        if result.strip().lower().startswith(META_STARTS):
            print("[Lit Review Agent] Meta-response on retry, using fallback.")
            return fallback_litreview("Meta-response detected twice.")
        return result
    except Exception as exc:
        print(f"Lit Review agent failed; using fallback. Reason: {exc}")
        return fallback_litreview(str(exc))