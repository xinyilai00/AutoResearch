from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from config import AGENT_ID, API_KEY, BASE_URL, PRINCIPAL_ID


DEFAULT_MODEL = os.environ.get("PAPER_AGENT_MODEL", "gpt-4.1")
DEFAULT_BASE_URL = BASE_URL or "https://api.openai.com/v1"


STAGE_PLACEHOLDERS = {
    "pi": "PI stage is not implemented yet. Treat the user prompt as the provisional structured search query.",
    "part1_literature": "Part 1 Literature stage is not implemented yet. Mark literature claims as TODO and do not invent citations.",
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
8. References

Rules:
- Do not fabricate citations, datasets, statistics, experiments, or results.
- If a prior stage is missing, explicitly label it as missing or provisional.
- Keep Results separate from Discussion.
- Use verified citations only when provided.
- Include graph, table, workflow diagram, and picture references where useful.
- For each visual, include caption, data source/provenance, and generation prompt.
- End with a "Figure Generation Notes" subsection before References.
"""


@dataclass
class AgentConfig:
    model: str
    iterations: int
    output_dir: Path
    temperature: float
    max_tokens: int
    review_agents: list[str]
    quality_threshold: int
    pivot_threshold: int
    max_pivots: int
    memory_path: Path


@dataclass
class ReviewScore:
    novelty: int
    correctness: int
    evidence: int
    clarity: int
    reproducibility: int

    @property
    def total(self) -> int:
        return self.novelty + self.correctness + self.evidence + self.clarity + self.reproducibility


@dataclass
class Review:
    score: ReviewScore
    strengths: list[str]
    weaknesses: list[str]
    revision_plan: list[str]


@dataclass
class Decision:
    action: str
    reason: str
    score_total: int


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
        del temperature, max_tokens

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Principal-Id": self.principal_id,
        }

        body = {
            "agentId": self.agent_id,
            "userInput": f"{system}\n\n{user}",
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/agent/run/async",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Agent request failed with HTTP {exc.code}: {body_text}") from exc

        request_id = result["data"]["requestId"]
        return self._read_stream(request_id)

    def _read_stream(self, request_id: str) -> str:
        from urllib.parse import urlencode
        import socket

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Principal-Id": self.principal_id,
        }

        query = urlencode({"requestId": request_id})
        request = urllib.request.Request(
            f"{self.base_url}/api/agent/run/stream?{query}",
            headers=headers,
            method="GET",
        )

        full_response = ""

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                while True:
                    try:
                        raw_line = response.readline()
                    except socket.timeout:
                        if full_response.strip():
                            print("Stream timed out after partial response; continuing with partial text.")
                            return full_response.strip()
                        raise RuntimeError("Agent stream timed out before returning any text.")

                    if not raw_line:
                        break

                    line = raw_line.decode("utf-8", errors="replace").strip()

                    if not line.startswith("data:"):
                        continue

                    try:
                        data = json.loads(line[5:])
                    except json.JSONDecodeError:
                        continue

                    if data.get("eventType") == "TEXT_DELTA":
                        full_response += data.get("data", {}).get("text", "")

                    if data.get("eventType") in {"RUN_COMPLETED", "DONE", "COMPLETED"}:
                        break

        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Agent stream failed with HTTP {exc.code}: {body_text}") from exc
        except urllib.error.URLError as exc:
            if full_response.strip():
                print("Stream connection failed after partial response; continuing with partial text.")
                return full_response.strip()
            raise RuntimeError(f"Agent stream failed before returning text: {exc}") from exc

        if not full_response.strip():
            raise RuntimeError("Agent stream ended without returning text.")

        return full_response.strip()

class TemplateFallbackModel(ChatModel):
    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> str:
        del system, temperature, max_tokens

        if "Return JSON" in user:
            return json.dumps(
                {
                    "novelty": 2,
                    "correctness": 2,
                    "evidence": 1,
                    "clarity": 3,
                    "reproducibility": 1,
                    "strengths": ["The draft has a recognizable structure."],
                    "weaknesses": ["Evidence and citations are placeholders."],
                    "revision_plan": ["Replace placeholders with real stage outputs."],
                }
            )

        if "visual artifact manifest" in user.lower():
            return fallback_visual_manifest()

        return fallback_paper()


def fallback_paper() -> str:
    return """# Provisional Research Paper Draft

## Abstract
This is a provisional paper draft generated without live API output or complete upstream stage artifacts. The paper structure is present, but literature claims, citations, experiments, and results must be replaced with verified outputs from the full pipeline.

## Introduction
The topic is treated as provisional. The PI, Literature, Proposal, Experiment, and Citations stages should provide the evidence needed to turn this into a submission-ready paper.

![Workflow overview](figures/figure_01_workflow.png)

## Review
The literature review is pending. This section should synthesize verified prior work, debates, methods, datasets, and gaps once the Literature stage is available.

![Literature map](figures/figure_02_literature_map.png)

## Methodology
The methodology is provisional. Once the Proposal and Experiment stages exist, this section should describe data, collection, experimental setup, variables, metrics, and analysis.

![Methodology schematic](figures/figure_03_methodology_schematic.png)

## Results
Results are pending. No completed findings, statistics, or performance claims are available yet.

![Results chart placeholder](figures/figure_04_results_chart.png)

## Discussion
Because results are pending, interpretation is limited. The final version should explain whether the hypothesis was supported, compare findings to literature, and describe limitations.

![Limitations matrix](figures/figure_05_limitations_matrix.png)

## Conclusion
This draft verifies that the Paper stage can run before all upstream agents exist. The next step is to replace placeholders with real outputs from PI, Literature, Proposal, Experiment, and Citations.

## Figure Generation Notes
- figures/figure_01_workflow.png: Workflow diagram; illustrative.
- figures/figure_02_literature_map.png: Requires verified literature clusters.
- figures/figure_03_methodology_schematic.png: Requires final experiment design.
- figures/figure_04_results_chart.png: Requires observed experiment results.
- figures/figure_05_limitations_matrix.png: Derived from review and claim audit.

## References
TODO: Add verified citations from Citations stage.
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

        stage_inputs["pi"] = run_pi_agent(
            args.prompt,
            Path(args.out) / "stage_outputs" / "pi_output.md",
        )

    cli_inputs = {
        "pi": args.pi_output,
        "part1_literature": args.part1_literature,
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

Write careful academic prose. Do not fabricate citations, datasets, statistics,
experiments, graphs, or results. If evidence is missing, label it as missing,
pending, provisional, or TODO.

The final paper must be at least 4,000 words when API generation is available.
"""


def build_plan(model: ChatModel, source: str, stage_inputs: str, config: AgentConfig) -> str:
    prompt = f"""Create a research paper plan.

{PAPER_REQUIREMENTS}

Source:
{source}

Stage inputs:
{stage_inputs}
"""
    return model.complete(system_prompt(), prompt, temperature=config.temperature, max_tokens=config.max_tokens)


def write_draft(model: ChatModel, source: str, stage_inputs: str, plan: str, config: AgentConfig) -> str:
    prompt = f"""Write the full research paper draft.

{PAPER_REQUIREMENTS}

Source:
{source}

Stage inputs:
{stage_inputs}

Plan:
{plan}
"""
    return model.complete(system_prompt(), prompt, temperature=config.temperature, max_tokens=config.max_tokens)


def review_draft(model: ChatModel, draft: str, config: AgentConfig, perspective: str) -> Review:
    prompt = f"""Review this draft as a strict {perspective} reviewer.

Return JSON with this exact schema:
{{
  "novelty": 1-5,
  "correctness": 1-5,
  "evidence": 1-5,
  "clarity": 1-5,
  "reproducibility": 1-5,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "revision_plan": ["..."]
}}

Penalize:
- under 4,000 words
- missing required sections
- fabricated citations/results
- missing visual provenance
- unclear placeholder handling

Return ONLY valid JSON. Do not include markdown fences, comments, explanations, or extra text.
Draft:
{draft}
"""
    raw = model.complete(system_prompt(), prompt, temperature=0.0, max_tokens=1800)
    
    try:
        data = parse_json_object(raw)
    except Exception as exc:
        print("Reviewer did not return valid JSON; using fallback review.")
        print(f"Reason: {exc}")
        data = {
            "novelty": 2,
            "correctness": 2,
            "evidence": 1,
            "clarity": 2,
            "reproducibility": 1,
            "strengths": ["The paper draft was generated."],
            "weaknesses": ["Reviewer output was not valid JSON, so this review is a fallback."],
            "revision_plan": ["Ask the reviewer agent to return strict JSON only."],
        }

    score = ReviewScore(
        novelty=clamp_score(data.get("novelty")),
        correctness=clamp_score(data.get("correctness")),
        evidence=clamp_score(data.get("evidence")),
        clarity=clamp_score(data.get("clarity")),
        reproducibility=clamp_score(data.get("reproducibility")),
    )

    return Review(
        score=score,
        strengths=list_strings(data.get("strengths")),
        weaknesses=list_strings(data.get("weaknesses")),
        revision_plan=list_strings(data.get("revision_plan")),
    )


def revise_draft(model: ChatModel, draft: str, review: Review, config: AgentConfig) -> str:
    prompt = f"""Revise the paper using this review.

Rules:
- Output the complete revised paper, not a diff.
- Preserve truthful uncertainty.
- Do not fabricate citations, data, figures, or results.
- Keep the paper at least 4,000 words when possible.
- Improve visual references and Figure Generation Notes.

Review:
{json.dumps(asdict(review), indent=2)}

Draft:
{draft}
"""
    return model.complete(system_prompt(), prompt, temperature=config.temperature, max_tokens=config.max_tokens)


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


def decide_next(review: Review, iteration: int, config: AgentConfig, pivot_count: int) -> Decision:
    total = review.score.total

    if total >= config.quality_threshold:
        return Decision("PROCEED", "quality threshold reached", total)

    if total <= config.pivot_threshold and pivot_count < config.max_pivots:
        return Decision("PIVOT", "score is below pivot threshold", total)

    if iteration >= config.iterations:
        return Decision("PROCEED", "iteration budget exhausted", total)

    return Decision("REFINE", "quality below threshold", total)


def parse_json_object(text: str) -> dict:
    text = text.strip()

    # Remove common markdown fences.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    # First try direct JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Then extract the first balanced JSON object.
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model output:\n{text[:500]}")

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : index + 1]
                return json.loads(candidate)

    raise ValueError(f"Could not parse JSON object from model output:\n{text[:500]}")


def clamp_score(value: object) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 1

    return max(1, min(5, score))


def list_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def format_review(review: Review) -> str:
    return "\n".join(
        [
            "# Review",
            "",
            "## Scores",
            f"- Novelty: {review.score.novelty}/5",
            f"- Correctness: {review.score.correctness}/5",
            f"- Evidence: {review.score.evidence}/5",
            f"- Clarity: {review.score.clarity}/5",
            f"- Reproducibility: {review.score.reproducibility}/5",
            f"- Total: {review.score.total}/25",
            "",
            "## Strengths",
            *format_bullets(review.strengths),
            "",
            "## Weaknesses",
            *format_bullets(review.weaknesses),
            "",
            "## Revision Plan",
            *format_bullets(review.revision_plan),
        ]
    )


def format_bullets(items: Iterable[str]) -> list[str]:
    rows = [f"- {item}" for item in items]
    return rows or ["- None provided."]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def read_source(args: argparse.Namespace) -> tuple[str, dict[str, str]]:
    pieces = []

    if args.prompt:
        pieces.append(args.prompt.strip())

    if args.paper:
        path = Path(args.paper)
        pieces.append(path.read_text(encoding="utf-8"))

    if not pieces:
        raise SystemExit("Provide --prompt, --paper, or both.")

    stage_inputs = collect_stage_inputs(args)
    return "\n\n".join(pieces), stage_inputs


def run_agent(args: argparse.Namespace) -> Path:
    source, stage_inputs = read_source(args)
    output_dir = Path(args.out).resolve()

    config = AgentConfig(
        model=args.model,
        iterations=args.iterations,
        output_dir=output_dir,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        review_agents=[agent.strip() for agent in args.review_agents.split(",") if agent.strip()],
        quality_threshold=args.quality_threshold,
        pivot_threshold=args.pivot_threshold,
        max_pivots=args.max_pivots,
        memory_path=Path(args.memory).expanduser().resolve(),
    )

    model = choose_model(config.model)
    formatted_stage_inputs = format_stage_inputs(stage_inputs)

    write(output_dir / "source.md", source)
    write(output_dir / "stage_inputs.md", formatted_stage_inputs)
    write(output_dir / "stage_inputs.json", json.dumps(stage_inputs, indent=2))
    write(
        output_dir / "config.json",
        json.dumps(
            {
                **asdict(config),
                "output_dir": str(config.output_dir),
                "memory_path": str(config.memory_path),
            },
            indent=2,
        ),
    )

    print("Planning paper...")
    plan = build_plan(model, source, formatted_stage_inputs, config)
    write(output_dir / "plan.md", plan)

    print("Writing initial draft...")
    draft = write_draft(model, source, formatted_stage_inputs, plan, config)
    write(output_dir / "draft_00.md", draft)
    write(output_dir / "figures" / "visual_manifest_00.md", generate_visual_manifest(model, draft, config))

    best_draft = draft
    pivot_count = 0

    for iteration in range(1, config.iterations + 1):
        print(f"Reviewing iteration {iteration}...")

        reviews = [
            review_draft(model, best_draft, config, perspective)
            for perspective in config.review_agents
        ]
        review = aggregate_reviews(reviews)

        write(output_dir / f"review_{iteration:02d}.md", format_review(review))
        append_jsonl(
            output_dir / "scores.jsonl",
            {
                "iteration": iteration,
                "score": asdict(review.score),
                "total": review.score.total,
                "timestamp": int(time.time()),
            },
        )

        decision = decide_next(review, iteration, config, pivot_count)
        append_jsonl(output_dir / "decisions.jsonl", asdict(decision) | {"iteration": iteration})

        if decision.action == "PROCEED":
            print(f"Decision: PROCEED ({decision.reason})")
            break

        print(f"Decision: {decision.action} ({decision.reason})")

        if decision.action == "PIVOT":
            pivot_count += 1

        best_draft = revise_draft(model, best_draft, review, config)
        write(output_dir / f"draft_{iteration:02d}.md", best_draft)
        write(
            output_dir / "figures" / f"visual_manifest_{iteration:02d}.md",
            generate_visual_manifest(model, best_draft, config),
        )

    final_review = aggregate_reviews(
        [review_draft(model, best_draft, config, perspective) for perspective in config.review_agents]
    )
    write(output_dir / "final_review.md", format_review(final_review))
    write(output_dir / "final.md", best_draft)
    write(output_dir / "best.md", best_draft)
    write(output_dir / "figures" / "visual_manifest_final.md", generate_visual_manifest(model, best_draft, config))

    return output_dir


def aggregate_reviews(reviews: list[Review]) -> Review:
    if not reviews:
        raise ValueError("No reviews to aggregate")

    count = len(reviews)

    score = ReviewScore(
        novelty=round(sum(review.score.novelty for review in reviews) / count),
        correctness=round(sum(review.score.correctness for review in reviews) / count),
        evidence=round(sum(review.score.evidence for review in reviews) / count),
        clarity=round(sum(review.score.clarity for review in reviews) / count),
        reproducibility=round(sum(review.score.reproducibility for review in reviews) / count),
    )

    strengths = []
    weaknesses = []
    revision_plan = []

    for review in reviews:
        strengths.extend(review.strengths)
        weaknesses.extend(review.weaknesses)
        revision_plan.extend(review.revision_plan)

    return Review(score=score, strengths=strengths, weaknesses=weaknesses, revision_plan=revision_plan)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and iteratively improve a research paper.",
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
    parser.add_argument("--research-question", help="Selected research question text or file path.")
    parser.add_argument("--deep-literature", help="Deep literature review output text or file path.")
    parser.add_argument("--proposal", help="Proposal/hypothesis output text or file path.")
    parser.add_argument("--experiment", help="Experiment process/results output text or file path.")
    parser.add_argument("--citations", help="Verified citations output text or file path.")

    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-tokens", type=int, default=14000)
    parser.add_argument("--review-agents", default="novelty,method,evidence,clarity,reproducibility")
    parser.add_argument("--quality-threshold", type=int, default=21)
    parser.add_argument("--pivot-threshold", type=int, default=10)
    parser.add_argument("--max-pivots", type=int, default=1)
    parser.add_argument("--memory", default="paper_runs/evolution/lessons.jsonl")

    return parser.parse_args()


if __name__ == "__main__":
    output_path = run_agent(parse_args())
    print(f"Done. Final paper: {output_path / 'final.md'}")