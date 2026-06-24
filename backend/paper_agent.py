from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

try:
    from .config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
    from .planner_agent import run_planner_agent
    from .intro_agent import run_intro_agent
    from .litreview_agent import run_litreview_agent
    from .methodology_agent import run_methodology_agent
    from .results_agent import run_results_agent
    from .conclusion_agent import run_conclusion_agent
    from .finalization_agent import run_finalization_agent
except ImportError:
    from config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
    from planner_agent import run_planner_agent
    from intro_agent import run_intro_agent
    from litreview_agent import run_litreview_agent
    from methodology_agent import run_methodology_agent
    from results_agent import run_results_agent
    from conclusion_agent import run_conclusion_agent
    from finalization_agent import run_finalization_agent


DEFAULT_MODEL = os.environ.get("PAPER_AGENT_MODEL", MODEL)
DEFAULT_BASE_URL = BASE_URL or "https://api.openai.com/v1"


STAGE_PLACEHOLDERS = {
    "pi": "PI stage is not implemented yet. Treat the user prompt as the provisional structured search query.",
    "part1_literature": "Part 1 Literature stage is not implemented yet. Mark literature claims as TODO and do not invent citations.",
    "research_questions": "Research Question stage is not implemented yet. Generate candidate questions before selecting a final one.",
    "research_question": "No selected research question was provided. Infer a narrow provisional question and label it provisional.",
    "deep_literature": "Deep Literature stage is not implemented yet. Identify methodologies, datasets, and prior results still needed.",
    "proposal": "Proposal stage is not implemented yet. Draft a provisional hypothesis, variables, design, and success criteria.",
    "experiment": "Experiment stage is not implemented yet. Treat results as pending; do not report completed findings or numbers.",
    "citations": "Citations stage is not implemented yet. Use TODO references only; do not fabricate bibliographic records.",
}


@dataclass
class AgentConfig:
    model: str
    output_dir: Path
    temperature: float
    max_tokens: int


def author_year_label(authors: str, year: str, title: str = "") -> str:
    author_list = [author.strip() for author in authors.split(",") if author.strip()]
    clean_year = year.strip() or "n.d."

    if not author_list:
        title_words = [word.strip(":;,.") for word in title.split() if word.strip(":;,.")]
        lead = " ".join(title_words[:3]) if title_words else "Unknown"
        return f"{lead}, {clean_year}"

    first_author = author_list[0]
    surname = first_author.split()[-1] if first_author.split() else first_author
    if len(author_list) == 1:
        return f"{surname}, {clean_year}"
    if len(author_list) == 2:
        second_author = author_list[1]
        second_surname = second_author.split()[-1] if second_author.split() else second_author
        return f"{surname} & {second_surname}, {clean_year}"
    return f"{surname} et al., {clean_year}"


def citation_lookup_from_stage_inputs(stage_inputs: str) -> dict[str, str]:
    lookup: dict[str, str] = {}
    lines = stage_inputs.splitlines()
    citation_index = 1
    for index, line in enumerate(lines):
        citation_match = re.match(r"^Citation:\s*\((.+)\)\s*$", line.strip(), flags=re.IGNORECASE)
        if citation_match:
            lookup[str(citation_index)] = citation_match.group(1).strip()
            citation_index += 1
            continue

        match = re.match(r"^\[(\d+)\]\s+(.+?)\s+\((\d{4}|n\.d\.|N/A|)\)", line.strip())
        if not match:
            continue

        citation_number, title, year = match.groups()
        authors = ""
        if index + 1 < len(lines):
            author_match = re.match(r"^Authors:\s*(.+)$", lines[index + 1].strip(), flags=re.IGNORECASE)
            if author_match:
                authors = author_match.group(1)
                if authors.upper() == "N/A":
                    authors = ""

        lookup[citation_number] = author_year_label(authors, year or "n.d.", title)
    return lookup


def replace_numeric_citation_markers(draft: str, citation_lookup: dict[str, str]) -> str:
    def replacement(match: re.Match[str]) -> str:
        raw_marker = match.group(1).strip()
        if "-" in raw_marker:
            bounds = [part.strip() for part in raw_marker.split("-", 1)]
            if all(part.isdigit() for part in bounds):
                start, end = int(bounds[0]), int(bounds[1])
                labels = [
                    citation_lookup.get(str(index), "citation TODO: author-year needed")
                    for index in range(start, end + 1)
                ]
                return "(" + "; ".join(labels) + ")"

        raw_numbers = re.split(r"\s*,\s*", raw_marker)
        labels = []
        for number in raw_numbers:
            label = citation_lookup.get(number)
            if label:
                labels.append(label)
            else:
                labels.append("citation TODO: author-year needed")
        return "(" + "; ".join(labels) + ")"

    return re.sub(r"\[(\d+(?:\s*,\s*\d+)*|\d+\s*-\s*\d+)\]", replacement, draft)


def looks_like_meta_response(text: str) -> bool:
    lowered = text.strip().lower()
    meta_starts = (
        "i'll write",
        "i will write",
        "i'll create",
        "i will create",
        "i'll prepare",
        "i will prepare",
        "here is",
        "i can",
        "let me",
        "it looks like",
        "the research paper has been completed",
        "the paper has been completed",
        "the manuscript has been completed",
        "the research paper is complete",
        "the paper is complete",
    )
    meta_phrases = (
        "key aspects of the paper",
        "containing all eight required sections",
        "has been completed and delivered",
        "the draft has been completed",
    )
    return (
        (lowered.startswith(meta_starts) and len(text.split()) < 500)
        or any(phrase in lowered[:1200] for phrase in meta_phrases)
    )


def has_required_paper_sections(text: str) -> bool:
    lowered = text.lower()
    required = (
        "abstract",
        "introduction",
        "literature review",
        "methodology",
        "results",
        "discussion",
        "conclusion",
        "references",
    )
    if not re.search(r"(?m)^#\s+\S+", text):
        return False
    return all(re.search(rf"(?m)^##?\s+.*{section}", lowered) for section in required)


def fallback_paper() -> str:
    return """# Provisional Research Paper Draft

## Abstract
This is a provisional research paper draft generated without a successful live paper-generation API response.

## Introduction
The research topic is treated as provisional until all upstream stages provide complete evidence.

## Literature Review
The literature review is pending or incomplete.

## Methodology
The methodology is provisional pending Proposal and Experiment stage completion.

## Results
Results are pending. No completed findings are reported in this provisional draft.

## Discussion
Because experiment results are pending, interpretation is limited.

## Conclusion
This draft confirms the Paper stage can run before all upstream stages are complete.

## References
TODO: Add verified citations from the Citations stage.
"""


def normalize_paper_draft(draft: str, stage_inputs: str = "") -> str:
    draft = draft.strip()
    if not draft:
        return fallback_paper()
    if looks_like_meta_response(draft) or not has_required_paper_sections(draft):
        print("Paper model returned a summary or incomplete draft; using provisional fallback draft.")
        return fallback_paper()
    return replace_numeric_citation_markers(draft, citation_lookup_from_stage_inputs(stage_inputs))


def read_optional_text(value: str | None, label: str) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    if any(sep in value for sep in ("/", "\\")) or value.endswith((".md", ".txt", ".json")):
        raise SystemExit(f"{label} file not found: {value}")
    return value.strip()


def collect_stage_inputs(args: argparse.Namespace) -> dict[str, str]:
    stage_inputs = dict(STAGE_PLACEHOLDERS)

    if args.stage_inputs_json:
        path = Path(args.stage_inputs_json)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit("--stage-inputs-json must contain a JSON object")
        for key in STAGE_PLACEHOLDERS:
            if payload.get(key):
                stage_inputs[key] = str(payload[key]).strip()

    cli_inputs = {
        "pi": args.pi_output,
        "part1_literature": args.part1_literature,
        "research_questions": args.research_questions,
        "research_question": args.research_question,
        "deep_literature": args.deep_literature,
        "proposal": args.proposal,
        "experiment": args.experiment,
        "citations": args.citations,
    }
    for key, value in cli_inputs.items():
        loaded = read_optional_text(value, key)
        if loaded:
            stage_inputs[key] = loaded

    return stage_inputs


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_source(args: argparse.Namespace) -> tuple[str, dict[str, str]]:
    pieces = []
    if args.prompt:
        pieces.append(args.prompt.strip())
    if args.paper:
        pieces.append(Path(args.paper).read_text(encoding="utf-8"))
    if not pieces:
        raise SystemExit("Provide --prompt, --paper, or both.")
    return "\n\n".join(pieces), collect_stage_inputs(args)


def run_agent(args: argparse.Namespace) -> Path:
    source, stage_inputs = read_source(args)
    output_dir = Path(args.out).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    write(output_dir / "source.md", source)
    write(output_dir / "stage_inputs.json", json.dumps(stage_inputs, indent=2))

    # Step 1: Planner
    print("[Paper Agent] Running planner...")
    planner_briefs = run_planner_agent(
        topic=source,
        pi_output=stage_inputs.get("pi", ""),
        lit_p1=stage_inputs.get("part1_literature", ""),
        lit_p2=stage_inputs.get("deep_literature", ""),
        research_question=stage_inputs.get("research_question", ""),
        proposal=stage_inputs.get("proposal", ""),
        experiment=stage_inputs.get("experiment", ""),
    )

    # DEBUG: save planner output
    write(output_dir / "planner_output.json", json.dumps(planner_briefs, indent=2))

    # Step 2: Inner agents in parallel
    print("[Paper Agent] Running inner agents in parallel...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            "intro": executor.submit(run_intro_agent, planner_briefs["intro"]),
            "litreview": executor.submit(run_litreview_agent, planner_briefs["litreview"]),
            "methodology": executor.submit(run_methodology_agent, planner_briefs["methodology"]),
            "results": executor.submit(run_results_agent, planner_briefs["results"]),
            "conclusion": executor.submit(run_conclusion_agent, planner_briefs["conclusion"]),
        }
        intro = futures["intro"].result()
        litreview = futures["litreview"].result()
        methodology = futures["methodology"].result()
        results = futures["results"].result()
        conclusion = futures["conclusion"].result()

    # Save individual section outputs for debugging
    paper_sections_dir = output_dir / "paper_sections"
    write(paper_sections_dir / "intro.md", intro)
    write(paper_sections_dir / "litreview.md", litreview)
    write(paper_sections_dir / "methodology.md", methodology)
    write(paper_sections_dir / "results.md", results)
    write(paper_sections_dir / "conclusion.md", conclusion)

    # Step 3: Finalization
    print("[Paper Agent] Running finalization...")
    draft = run_finalization_agent(
        planner_output=planner_briefs,
        intro=intro,
        litreview=litreview,
        methodology=methodology,
        results=results,
        conclusion=conclusion,
    )

    draft = normalize_paper_draft(draft)
    write(output_dir / "final.md", draft)
    write(output_dir / "best.md", draft)

    return output_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a research paper draft from previous stage outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Config:
              config.py must expose BASE_URL, API_KEY, AGENT_ID, PRINCIPAL_ID.
            """
        ),
    )
    parser.add_argument("--prompt", help="Research prompt to turn into a paper.")
    parser.add_argument("--paper", help="Path to a Markdown or text seed paper.")
    parser.add_argument("--out", default="paper_runs/latest", help="Output directory.")
    parser.add_argument("--stage-inputs-json", help="JSON object containing upstream stage outputs.")
    parser.add_argument("--pi-output", help="PI search query output text or file path.")
    parser.add_argument("--part1-literature", help="Part 1 literature output text or file path.")
    parser.add_argument("--research-questions", help="Candidate research questions output text or file path.")
    parser.add_argument("--research-question", help="Selected research question text or file path.")
    parser.add_argument("--deep-literature", help="Deep literature review output text or file path.")
    parser.add_argument("--proposal", help="Proposal/hypothesis output text or file path.")
    parser.add_argument("--experiment", help="Experiment process/results output text or file path.")
    parser.add_argument("--citations", help="Verified citations output text or file path.")
    parser.add_argument("--iterations", type=int, default=0, help="Ignored.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-tokens", type=int, default=14000)
    parser.add_argument("--review-agents", default="", help="Ignored.")
    parser.add_argument("--quality-threshold", type=int, default=21, help="Ignored.")
    parser.add_argument("--pivot-threshold", type=int, default=10, help="Ignored.")
    parser.add_argument("--max-pivots", type=int, default=1, help="Ignored.")
    parser.add_argument("--memory", default="paper_runs/evolution/lessons.jsonl", help="Ignored.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    output_path = run_agent(parse_args())
    print(f"Done. Final paper: {output_path / 'final.md'}")