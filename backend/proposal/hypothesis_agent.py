from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ..agent_api import call_agent_api
    from ..config import HYPOTHESIS_PRINCIPAL_ID
except ImportError:
    from agent_api import call_agent_api
    from config import HYPOTHESIS_PRINCIPAL_ID


HYPOTHESIS_PROMPT = """
You are the Hypothesis Agent in an autonomous research pipeline.

Input:
- selected research question
- deep literature review
- dataset candidates and schema inspection results, when available

Job:
Create only the hypothesis-level proposal plan. Do not search datasets and do not create an execution spec.
The hypothesis must be testable using the provided dataset/schema context.

Rules:
- Treat "experiment" as a public-data analysis experiment.
- Do not propose lab experiments, surveys, physical sensor deployments, or new private data collection.
- Prefer a hypothesis that uses real dataset columns or target candidates from the schema context.
- If a schema target candidate exists, choose one and name it as the dependent variable.
- If no target candidate exists but rows loaded, use AUTO_TARGET and explain that the Experiment Agent should infer the target after loading.
- If no readable schema exists, clearly mark the hypothesis as provisional.
- State what data characteristics are required for the analysis to be executable.
- Do not fabricate citations, datasets, statistics, or results.
- Use author-year citations only if they are present in the input.

Output exactly:
RESEARCH QUESTION:
[question]

HYPOTHESIS:
[testable hypothesis]

ANALYSIS GOAL:
[what the analysis must determine]

REQUIRED DATA CHARACTERISTICS:
- [required columns/labels/populations/time range/etc.]

KEY VARIABLES:
- Independent variables: [...]
- Dependent variables: [...]
- Control variables: [...]

SUCCESS CRITERIA:
- [metric/comparison that would support the hypothesis]
"""


def read_text_or_path(value: str | Path) -> str:
    path = Path(value)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return str(value)


def fallback_hypothesis(research_question: str, reason: str) -> str:
    return f"""RESEARCH QUESTION:
{research_question}

HYPOTHESIS:
TO_VERIFY: A testable hypothesis could not be generated because the Hypothesis Agent was unavailable.

ANALYSIS GOAL:
Define a public-data analysis that can test the research question without collecting new private data.

REQUIRED DATA CHARACTERISTICS:
- Public/downloadable dataset files.
- Measurable outcome column relevant to the research question.
- Feature columns sufficient for a baseline analysis.

KEY VARIABLES:
- Independent variables: TO_VERIFY
- Dependent variables: TO_VERIFY
- Control variables: TO_VERIFY

SUCCESS CRITERIA:
- The analysis uses reproducible public data.
- The target variable and metric are explicit.

Fallback reason: {reason}
"""


def schema_context_text(dataset_report: dict | None, schema_report: dict | None) -> str:
    if not dataset_report and not schema_report:
        return "No dataset/schema context was provided."
    return (
        "Dataset Agent output:\n"
        f"{json.dumps(dataset_report or {}, indent=2)}\n\n"
        "Schema Agent output:\n"
        f"{json.dumps(schema_report or {}, indent=2)}"
    )


def run_hypothesis_agent(
    research_question: str,
    deep_literature_review: str,
    dataset_report: dict | None = None,
    schema_report: dict | None = None,
) -> str:
    prompt = f"""{HYPOTHESIS_PROMPT}

Selected research question:
{research_question}

Deep literature review:
{deep_literature_review}

Dataset and schema context:
{schema_context_text(dataset_report, schema_report)}
"""
    try:
        return call_agent_api(prompt, "Hypothesis", HYPOTHESIS_PRINCIPAL_ID)
    except Exception as exc:
        print(f"Hypothesis failed; using fallback. Reason: {exc}")
        return fallback_hypothesis(research_question, str(exc))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate hypothesis-level proposal plan.")
    parser.add_argument("research_question")
    parser.add_argument("--deep-literature", default="")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(run_hypothesis_agent(args.research_question, read_text_or_path(args.deep_literature)))
