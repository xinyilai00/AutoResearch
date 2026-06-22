from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path

from config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API


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


PAPER_REQUIREMENTS = """
Write a complete academic research paper of at least 4,000 words.

Required sections, in order:
1. Abstract
2. Introduction
3. Review
4. Methodology
5. Results
6. Discussion
7. Conclusion
8. Figure Generation Notes
9. References

Rules:
- Do not fabricate citations, datasets, statistics, experiments, or results.
- If a prior stage is missing, explicitly label it as missing or provisional.
- Keep Results separate from Discussion.
- Use verified citations only when provided.
- Include graph, table, workflow diagram, and picture references where useful.
- For each visual, include caption, data source/provenance, and generation prompt.
- Output only the paper. Do not narrate your intent or mention PDF generation.
"""


@dataclass
class AgentConfig:
    model: str
    output_dir: Path
    temperature: float
    max_tokens: int


class ChatModel:
    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        raise NotImplementedError


class AICompatibleModel(ChatModel):
    def __init__(self, model: str, base_url: str = DEFAULT_BASE_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = API_KEY
        self.agent_id = AGENT_ID
        self.principal_id = PRINCIPAL_ID

        if not self.api_key:
            raise ValueError("API_KEY is not set")
        if not self.agent_id:
            raise ValueError("AGENT_ID is not set")
        if not self.principal_id:
            raise ValueError("PRINCIPAL_ID is not set")

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Principal-Id": self.principal_id,
        }
        body = {
            "agentId": self.agent_id,
            "userInput": f"{system}\n\n{user}",
        }

        if SEND_MODEL_TO_AGENT_API and self.model:
            body["model"] = self.model

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = requests.post(
                    f"{self.base_url}/api/agent/run/async",
                    headers=headers,
                    json=body,
                    timeout=180,
                )
                response.raise_for_status()
                request_id = response.json()["data"]["requestId"]
                return self._read_stream(request_id)
            except requests.exceptions.RequestException as exc:
                last_error = exc
                print(f"Paper API request failed on attempt {attempt}/3: {exc}")
                if attempt < 3:
                    time.sleep(5 * attempt)
            except RuntimeError as exc:
                last_error = exc
                print(f"Paper API stream failed on attempt {attempt}/3: {exc}")
                if attempt < 3:
                    time.sleep(5 * attempt)

        print(f"Paper API unavailable; using local fallback. Reason: {last_error}")
        return TemplateFallbackModel().complete(system, user, temperature=temperature, max_tokens=max_tokens)

    def _read_stream(self, request_id: str) -> str:
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Principal-Id": self.principal_id,
        }
        response = requests.get(
            f"{self.base_url}/api/agent/run/stream",
            headers=headers,
            params={"requestId": request_id},
            stream=True,
            timeout=(30, 300),
        )
        response.encoding = "utf-8"
        response.raise_for_status()

        full_response = ""
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:])
            except json.JSONDecodeError:
                continue

            event_type = data.get("eventType")
            if event_type in {"TEXT_START", "TEXT_DELTA"}:
                full_response += data.get("data", {}).get("text", "")
            if event_type in {"TEXT_END", "MESSAGE_COMPLETED", "RUN_COMPLETED", "DONE", "COMPLETED"}:
                if full_response.strip():
                    break

        if not full_response.strip():
            raise RuntimeError("Agent stream ended without returning text.")
        return full_response.strip()


class TemplateFallbackModel(ChatModel):
    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        del system, user, temperature, max_tokens
        return fallback_paper()


def fallback_paper() -> str:
    return """# Provisional Research Paper Draft

## Abstract
This is a provisional research paper draft generated without a successful live paper-generation API response. The draft preserves the required paper structure and marks missing evidence as pending rather than inventing citations, datasets, experiments, or results.

## Introduction
The research topic is treated as provisional until the upstream PI, Literature, Proposal, Experiment, and Citations stages provide complete evidence. The purpose of this draft is to verify that the Paper stage can produce a structured manuscript from available stage inputs.

![Workflow overview](figures/figure_01_workflow.png)

## Review
The literature review is pending or incomplete. A submission-ready paper should synthesize verified prior work, compare methods and datasets, identify gaps, and position the selected research question within those gaps.

![Literature map](figures/figure_02_literature_map.png)

## Methodology
The methodology is provisional. Once Proposal and Experiment stages are complete, this section should specify data sources, collection procedures, variables, metrics, baselines, statistical analysis, and reproducibility details.

![Methodology schematic](figures/figure_03_methodology_schematic.png)

## Results
Results are pending. No completed findings, statistical outcomes, or performance numbers are reported in this provisional draft.

![Results chart placeholder](figures/figure_04_results_chart.png)

## Discussion
Because experiment results are pending, interpretation is limited. The final version should explain whether the hypothesis was supported, compare findings with the literature, and state threats to validity.

![Limitations matrix](figures/figure_05_limitations_matrix.png)

## Conclusion
This draft confirms the Paper stage can run before all upstream stages are complete. The next version should replace placeholders with verified literature, proposal details, experiment results, and citations.

## Figure Generation Notes
- figures/figure_01_workflow.png: Workflow diagram; illustrative.
- figures/figure_02_literature_map.png: Requires verified literature clusters.
- figures/figure_03_methodology_schematic.png: Requires final experiment design.
- figures/figure_04_results_chart.png: Requires observed experiment results.
- figures/figure_05_limitations_matrix.png: Derived from review and claim audit.

## References
TODO: Add verified citations from the Citations stage.
"""


def fallback_visual_manifest() -> str:
    return """# Visual Artifact Manifest

## figures/figure_01_workflow.png
- Section: Introduction
- Type: workflow diagram
- Prompt: Create an academic workflow diagram showing PI, Literature, Proposal, Experiment, Paper, Review, Rebuttal, and Submission.
- Provenance: illustrative.

## figures/figure_02_literature_map.png
- Section: Review
- Type: literature map
- Prompt: Create a literature landscape map showing methods, datasets, debates, and gaps.
- Provenance: requires verified literature.

## figures/figure_03_methodology_schematic.png
- Section: Methodology
- Type: schematic
- Prompt: Create a methodology pipeline with inputs, analysis steps, variables, metrics, and validation checks.
- Provenance: requires proposal and experiment design.

## figures/figure_04_results_chart.png
- Section: Results
- Type: graph
- Prompt: Create a chart from observed experiment metrics.
- Provenance: requires real experiment results.

## figures/figure_05_limitations_matrix.png
- Section: Discussion
- Type: table
- Prompt: Create a limitations and threats-to-validity matrix.
- Provenance: derived from review and claim audit.
"""


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
        "review",
        "methodology",
        "results",
        "discussion",
        "conclusion",
        "references",
    )
    if not re.search(r"(?m)^#\s+\S+", text):
        return False
    return all(re.search(rf"(?m)^##?\s+.*{section}", lowered) for section in required)


def normalize_paper_draft(draft: str) -> str:
    draft = draft.strip()
    if not draft:
        return fallback_paper()
    if looks_like_meta_response(draft) or not has_required_paper_sections(draft):
        print("Paper model returned a summary or incomplete draft; using provisional fallback draft.")
        return fallback_paper()
    return draft


def choose_model(model_name: str) -> ChatModel:
    if API_KEY:
        return AICompatibleModel(model_name)
    print("API_KEY is not set; using local template fallback.")
    return TemplateFallbackModel()


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

    if args.run_pi:
        if not args.prompt:
            raise SystemExit("--run-pi requires --prompt")
        try:
            from pi_agent import run_pi_agent
        except ImportError as exc:
            raise SystemExit("Could not import pi_agent.py. Put it next to paper_agent.py.") from exc

        pi_result = run_pi_agent(args.prompt)
        stage_inputs["pi"] = pi_result
        pi_path = Path(args.out) / "stage_outputs" / "pi_output.md"
        pi_path.parent.mkdir(parents=True, exist_ok=True)
        pi_path.write_text(pi_result.rstrip() + "\n", encoding="utf-8")

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


def format_stage_inputs(stage_inputs: dict[str, str]) -> str:
    labels = {
        "pi": "PI Search Query",
        "part1_literature": "Part 1 Literature Review and Research Gaps",
        "research_questions": "Candidate Research Questions",
        "research_question": "Selected Research Question",
        "deep_literature": "Deep Literature Review",
        "proposal": "Proposal and Hypothesis",
        "experiment": "Experiment Process and Results",
        "citations": "Verified Citations",
    }
    parts = ["# Upstream Stage Inputs"]
    for key in STAGE_PLACEHOLDERS:
        parts.append(f"\n## {labels[key]}\n{stage_inputs[key]}")
    return "\n".join(parts)


def system_prompt() -> str:
    return """You are the Paper agent in an autonomous research pipeline.

Output the paper directly. Do not narrate your intentions. Do not say you will
write, create, prepare, generate, or produce a paper. Do not mention PDF
generation. Do not include assistant-style prefaces such as "Here is..." or
"I'll write...".

Write careful academic prose. Do not fabricate citations, datasets, statistics,
experiments, graphs, or results. If evidence is missing, label it as missing,
pending, provisional, or TODO.
"""


def write_draft(model: ChatModel, source: str, stage_inputs: str, config: AgentConfig) -> str:
    prompt = f"""Write the full research paper draft.

CRITICAL OUTPUT RULES:
- Output ONLY the paper itself.
- Do NOT say "I will write", "I'll write", "I'll create", "Here is", or describe what you are going to do.
- Do NOT mention creating a PDF.
- Start directly with the paper title as a Markdown H1 heading.
- The output must be a complete Markdown research paper.
- Target at least 4,000 words when API generation is available.

{PAPER_REQUIREMENTS}

Source:
{source}

Stage inputs:
{stage_inputs}
"""
    draft = model.complete(system_prompt(), prompt, temperature=config.temperature, max_tokens=config.max_tokens)
    if looks_like_meta_response(draft) or not has_required_paper_sections(draft):
        retry_prompt = f"""Your previous response was INVALID because it summarized completion instead of outputting the paper.

You must now output ONLY the full Markdown paper itself.

Hard rules:
- Start with a Markdown H1 title: # [paper title]
- Include these headings exactly: ## Abstract, ## Introduction, ## Review, ## Methodology, ## Results, ## Discussion, ## Conclusion, ## Figure Generation Notes, ## References.
- Do not say "I will", "I'll", "Here is", "completed", "delivered", or mention PDF generation.
- Do not summarize the paper. Write the actual paper body.
- Target at least 4,000 words when possible.

{PAPER_REQUIREMENTS}

Source:
{source}

Stage inputs:
{stage_inputs}
"""
        draft = model.complete(
            system_prompt(),
            retry_prompt,
            temperature=config.temperature,
            max_tokens=max(config.max_tokens, 14000),
        )
    return normalize_paper_draft(draft)


def generate_visual_manifest(model: ChatModel, draft: str, config: AgentConfig) -> str:
    prompt = f"""Create a visual artifact manifest for this paper.

Each entry must include:
- file path under figures/
- section placement
- visual type
- caption
- data source/provenance
- graph axes/units if applicable
- image-generation prompt
- verification checklist

Draft:
{draft}
"""
    return model.complete(system_prompt(), prompt, temperature=config.temperature, max_tokens=3000)


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
    config = AgentConfig(
        model=args.model,
        output_dir=output_dir,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    model = choose_model(config.model)
    formatted_stage_inputs = format_stage_inputs(stage_inputs)

    write(output_dir / "source.md", source)
    write(output_dir / "stage_inputs.md", formatted_stage_inputs)
    write(output_dir / "stage_inputs.json", json.dumps(stage_inputs, indent=2))

    print("Writing paper draft...")
    draft = write_draft(model, source, formatted_stage_inputs, config)
    write(output_dir / "final.md", draft)
    write(output_dir / "best.md", draft)

    print("Generating visual manifest...")
    #write(output_dir / "figures" / "visual_manifest_final.md", generate_visual_manifest(model, draft, config))

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
    parser.add_argument("--run-pi", action="store_true", help="Run pi_agent.py and use its output.")
    parser.add_argument("--pi-output", help="PI search query output text or file path.")
    parser.add_argument("--part1-literature", help="Part 1 literature output text or file path.")
    parser.add_argument("--research-questions", help="Candidate research questions output text or file path.")
    parser.add_argument("--research-question", help="Selected research question text or file path.")
    parser.add_argument("--deep-literature", help="Deep literature review output text or file path.")
    parser.add_argument("--proposal", help="Proposal/hypothesis output text or file path.")
    parser.add_argument("--experiment", help="Experiment process/results output text or file path.")
    parser.add_argument("--citations", help="Verified citations output text or file path.")

    # Kept for CLI compatibility; review iterations now belong to review_agent.py.
    parser.add_argument("--iterations", type=int, default=0, help="Ignored. Review iterations are handled by review_agent.py.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-tokens", type=int, default=14000)
    parser.add_argument("--review-agents", default="", help="Ignored. Review agents are handled by review_agent.py.")
    parser.add_argument("--quality-threshold", type=int, default=21, help="Ignored.")
    parser.add_argument("--pivot-threshold", type=int, default=10, help="Ignored.")
    parser.add_argument("--max-pivots", type=int, default=1, help="Ignored.")
    parser.add_argument("--memory", default="paper_runs/evolution/lessons.jsonl", help="Ignored.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    output_path = run_agent(parse_args())
    print(f"Done. Final paper: {output_path / 'final.md'}")
