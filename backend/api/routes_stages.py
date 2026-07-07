from __future__ import annotations

import os
import json
from datetime import datetime, timezone

from pathlib import Path
from typing import Optional
from urllib import request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.feedback import apply_stage_feedback, normalize_stage_name
from backend.experiment_agent import run_experiment_stage
from backend.lit_agent_p1 import run_literature_stage
from backend.lit_agent_p2 import run_deep_literature_stage
from backend.paper_agent import parse_args as parse_paper_args
from backend.paper_agent import run_agent as run_paper_agent
from backend.pi_agent import run_pi_agent
from backend.pipeline_state import PipelineState, set_experiment_anchor
from backend.proposal_agent import run_proposal_stage
from backend.research_question_agent import run_research_question_stage
from backend.review_agent import run_review_from_file


router = APIRouter()


class StageRunRequest(BaseModel):
    topic: Optional[str] = None
    feedback: Optional[str] = None
    pi_output: Optional[str] = None
    literature: Optional[str] = None
    research_questions: Optional[str] = None
    research_question: Optional[str] = None
    deep_literature: Optional[str] = None
    proposal: Optional[str] = None
    experiment: Optional[str] = None
    paper: Optional[str] = None
    run_dir: str = "paper_runs/latest"
    repo_url: Optional[str] = None        # NEW
    hypothesis: Optional[str] = None      # NEW


class StageFeedbackRequest(BaseModel):
    feedback: str
    run_dir: str = "paper_runs/latest"


class SaveRunRequest(BaseModel):
    label: Optional[str] = None
    run_dir: str = "paper_runs/latest"


def read_output(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def response_for_path(stage: str, path: Path, state: PipelineState, status: str) -> dict:
    return {
        "stage": stage,
        "status": status,
        "output_path": str(path),
        "output": state.read_active_output(stage),
        "state": state.state,
    }


DOWNSTREAM_STAGES = {
    "pi": ["literature", "research_questions", "research_question", "deep_literature", "proposal", "repo_selection", "experiment", "paper", "review"],
    "literature": ["research_questions", "research_question", "deep_literature", "proposal", "repo_selection", "experiment", "paper", "review"],
    "research_questions": ["research_question", "deep_literature", "proposal", "repo_selection", "experiment", "paper", "review"],
    "research_question": ["deep_literature", "proposal", "repo_selection", "experiment", "paper", "review"],
    "deep_literature": ["proposal", "repo_selection", "experiment", "paper", "review"],
    "proposal": ["experiment", "paper", "review"],
    "experiment": ["paper", "review"],
    "paper": ["review"],
}


@router.post("/api/stages/{stage}/run")
def run_stage(stage: str, request: StageRunRequest) -> dict:
    print(f"DEBUG: received stage = {stage}")
    stage = normalize_stage_name(stage)
    print(f"DEBUG: normalized stage = {stage}")
    state = PipelineState(request.run_dir)
    if request.topic:
        state.set_metadata("topic", request.topic)
    state.clear_stages(DOWNSTREAM_STAGES.get(stage, []))

    try:
        if request.feedback:
            output_path = apply_stage_feedback(stage, request.feedback, request.run_dir)
            return response_for_path(stage, output_path, PipelineState(request.run_dir), "revised")

        output_path = run_stage_without_feedback(stage, request, state)
        return response_for_path(stage, output_path, state, "generated")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/stages/{stage}/feedback")
def submit_stage_feedback(stage: str, request: StageFeedbackRequest) -> dict:
    stage = normalize_stage_name(stage)
    try:
        output_path = apply_stage_feedback(stage, request.feedback, request.run_dir)
        state = PipelineState(request.run_dir)
        return response_for_path(stage, output_path, state, "revised")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def run_stage_without_feedback(stage: str, request: StageRunRequest, state: PipelineState) -> Path:
    if stage == "pi":
        if not request.topic:
            raise ValueError("PI stage requires topic.")
        output = run_pi_agent(request.topic)
        return state.write_stage_output("pi", output)

    if stage == "literature":
        topic = request.topic or state.get_metadata("topic")
        pi_output = request.pi_output or state.read_active_output("pi")
        if not topic or not pi_output:
            raise ValueError("Literature stage requires topic and PI output.")
        state.set_metadata("literature_citations", [])
        try:
            output = run_literature_stage(
                pi_output,
                topic,
                citation_callback=lambda links: state.set_metadata("literature_citations", links),
            )
        except Exception as e:
            print(f"DEBUG LITERATURE ERROR: {e}")
            raise
        return state.write_stage_output("literature", output)

    if stage == "research_questions":
        topic = request.topic or state.get_metadata("topic")
        literature = request.literature or state.read_active_output("literature")
        if not topic or not literature:
            raise ValueError("Research Questions stage requires topic and literature output.")
        try:
            output = run_research_question_stage(topic, literature)
        except Exception as e:
            print(f"DEBUG RESEARCH QUESTIONS ERROR: {e}")
            raise
        return state.write_stage_output("research_questions", output)

    if stage == "research_question":
        question = request.research_question
        if not question:
            raise ValueError("Research question stage requires research_question.")
        return state.write_stage_output("research_question", question)

    if stage == "deep_literature":
        question = request.research_question or state.read_active_output("research_question")
        if not question:
            raise ValueError("Deep Literature stage requires research_question.")
        state.set_metadata("deep_literature_citations", [])
        try:
            output = run_deep_literature_stage(
                question,
                citation_callback=lambda links: state.set_metadata("deep_literature_citations", links),
            )
        except Exception as e:
            print(f"DEBUG DEEP LITERATURE ERROR: {e}")
            raise
        return state.write_stage_output("deep_literature", output)

    if stage == "proposal":
        question = request.research_question or state.read_active_output("research_question")
        deep_literature = request.deep_literature or state.read_active_output("deep_literature")
        if not question or not deep_literature:
            raise ValueError("Proposal stage requires research_question and deep_literature.")

        from backend.repo_finder_agent import run_repo_finder_agent
        from backend.repo_assessor_agent import run_repo_assessor_agent
        from backend.progress import log, clear
        clear()
        log("[Proposal Stage] Starting repo search...")
        state.set_metadata("repo_candidates", [])
        state.set_metadata("repo_grades", [])
        state.set_metadata("selected_repo_name", None)
        state.set_metadata("selected_repo_url", None)
        state.set_metadata("selected_repo_reason", None)
        repos = run_repo_finder_agent(question)
        if not repos:
            raise RuntimeError("Repo finder returned no candidates.")
        state.set_metadata("repo_candidates", repos)
        log(f"[Proposal Stage] Repo finder returned {len(repos)} candidate(s).")

        selected_repo = run_repo_assessor_agent(
            repos,
            question,
            on_graded=lambda graded: state.set_metadata("repo_grades", graded),
        )
        if not selected_repo:
            raise RuntimeError("Repo assessor could not select a repo.")

        set_experiment_anchor(
            repo_url=selected_repo["url"],
            repo_name=selected_repo["name"],
            hypothesis=f"Using {selected_repo['name']}, this study investigates: {question.strip()}",
        )
        hypothesis = f"Using {selected_repo['name']}, this study investigates: {question.strip()}"
        state.set_metadata("selected_repo_id", selected_repo["name"])
        state.set_metadata("selected_repo_name", selected_repo["name"])
        state.set_metadata("selected_repo_url", selected_repo["url"])
        state.set_metadata("selected_repo_reason", selected_repo.get("reason", selected_repo.get("overall_assessment", "")))
        state.set_metadata("hypothesis", hypothesis)

        log(f"[Proposal Stage] Selected repo: {selected_repo['name']}. Generating proposal...")
        output = run_proposal_stage(question, deep_literature, selected_repo=selected_repo)
        log("[Proposal Stage] Proposal complete.")
        return state.write_stage_output("proposal", output)

    if stage == "experiment":
        proposal = request.proposal or state.read_active_output("proposal")
        if not proposal:
            raise ValueError("Experiment stage requires proposal output.")
        output = run_experiment_stage(proposal, state.run_dir / "experiment")
        if output.lstrip().startswith("# Experiment Failed"):
            status = "failed"
        elif "REDESIGN_NEEDED" in output:
            status = "redesign_needed"
        else:
            status = "generated"
        return state.write_stage_output("experiment", output, status=status)

    if stage == "paper":
        return run_paper_stage(request, state)

    if stage == "review":
        return run_review_stage(request, state)

    raise ValueError(f"Unsupported stage: {stage}")


def run_paper_stage(request: StageRunRequest, state: PipelineState) -> Path:
    topic = request.topic or state.get_metadata("topic") or "AutoResearch paper"
    paper_seed = request.paper
    args_list = [
        "--prompt", topic,
        "--pi-output", state.read_active_output("pi"),
        "--part1-literature", state.read_active_output("literature"),
        "--research-questions", state.read_active_output("research_questions"),
        "--research-question", state.read_active_output("research_question"),
        "--deep-literature", state.read_active_output("deep_literature"),
        "--proposal", state.read_active_output("proposal"),
        "--experiment", state.read_active_output("experiment"),
        "--out", str(state.run_dir),
        "--iterations", "0",
        "--max-tokens", "14000",
    ]
    if paper_seed:
        args_list.extend(["--paper", paper_seed])

    output_dir = run_paper_agent(parse_paper_args(args_list))
    final_path = output_dir / "final.md"
    state.set_stage_status("paper", "generated")

    if final_path.exists():
        state.write_stage_output("paper", final_path.read_text(encoding="utf-8"))

    return final_path


def run_review_stage(request: StageRunRequest, state: PipelineState) -> Path:
    draft_path = Path(request.paper) if request.paper else state.run_dir / "final.md"
    if not draft_path.exists():
        raise ValueError("Review stage requires an existing paper draft.")
    review_dir = run_review_from_file(draft_path, state.run_dir / "review", rounds=1)
    state.set_stage_status("review", "generated")
    return review_dir / "reviewed_draft.md"


SAVED_RUNS_DIR = Path("paper_runs/saved")
HISTORY_STAGES = [
    "pi",
    "literature",
    "research_questions",
    "research_question",
    "deep_literature",
    "proposal",
    "experiment",
    "paper",
    "review",
]


def stage_error_summary(stage: str, text: str, status: str) -> str:
    stripped = (text or "").strip()
    if status in {"failed", "redesign_needed"}:
        return stripped.splitlines()[0] if stripped else status
    if stripped.startswith("# Experiment Failed") or stripped.startswith("# Failed"):
        return stripped.splitlines()[0]
    if "COLAB_EXECUTOR_ERROR:" in stripped:
        return "Colab executor error"
    return ""


def build_run_snapshot(state: PipelineState, label: str | None = None) -> dict:
    saved_at = datetime.now(timezone.utc).isoformat()
    metadata = state.state.get("metadata", {})
    stages = {}
    errors = []
    for stage in HISTORY_STAGES:
        text = state.read_active_output(stage)
        status = state.state.get("stage_status", {}).get(stage, "not_run")
        active_ref = state.state.get("active_outputs", {}).get(stage)
        error = stage_error_summary(stage, text, status)
        stages[stage] = {
            "status": status,
            "active_ref": active_ref,
            "output": text,
            "preview": text[:500],
            "error": error,
        }
        if error:
            errors.append({"stage": stage, "message": error})

    experiment_dir = state.run_dir / "experiment"
    experiment_logs = {}
    for name in ["training_stdout.txt", "training_stderr.txt", "experiment_output.md"]:
        path = experiment_dir / name
        if path.exists():
            experiment_logs[name] = path.read_text(encoding="utf-8", errors="replace")

    return {
        "id": saved_at.replace(":", "").replace(".", ""),
        "label": (label or metadata.get("topic") or "Untitled run").strip(),
        "saved_at": saved_at,
        "summary": {
            "topic": metadata.get("topic", ""),
            "research_question": stages.get("research_question", {}).get("output", "").strip(),
            "selected_repo_name": metadata.get("selected_repo_name"),
            "selected_repo_url": metadata.get("selected_repo_url"),
            "stage_status": state.state.get("stage_status", {}),
            "errors": errors,
        },
        "metadata": metadata,
        "stages": stages,
        "experiment_logs": experiment_logs,
        "state": state.state,
        "output_store": state.output_store,
    }


def saved_run_summary(snapshot: dict) -> dict:
    summary = snapshot.get("summary", {})
    return {
        "id": snapshot.get("id"),
        "label": snapshot.get("label"),
        "saved_at": snapshot.get("saved_at"),
        "topic": summary.get("topic", ""),
        "research_question": summary.get("research_question", ""),
        "selected_repo_name": summary.get("selected_repo_name"),
        "selected_repo_url": summary.get("selected_repo_url"),
        "stage_status": summary.get("stage_status", {}),
        "errors": summary.get("errors", []),
    }


@router.post("/api/runs/save")
def save_current_run(request: SaveRunRequest) -> dict:
    state = PipelineState(request.run_dir)
    snapshot = build_run_snapshot(state, request.label)
    SAVED_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = SAVED_RUNS_DIR / f"{snapshot['id']}.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return {"saved": True, "run": saved_run_summary(snapshot)}


@router.get("/api/runs/saved")
def list_saved_runs() -> dict:
    SAVED_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for path in sorted(SAVED_RUNS_DIR.glob("*.json"), reverse=True):
        try:
            runs.append(saved_run_summary(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return {"runs": runs}


@router.get("/api/runs/saved/{run_id}")
def get_saved_run(run_id: str) -> dict:
    path = SAVED_RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Saved run not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/api/stages/{stage}/approve")
def approve_stage(stage: str, run_dir: str = "paper_runs/latest") -> dict:
    stage = normalize_stage_name(stage)
    state = PipelineState(run_dir)
    state.approve_stage(stage)
    return {
        "stage": stage,
        "status": "approved",
        "state": state.state,
    }


@router.get("/api/runs/latest")
def get_latest_run(run_dir: str = "paper_runs/latest") -> dict:
    return PipelineState(run_dir).state


@router.get("/api/stages/{stage}/output")
def get_stage_output(stage: str, run_dir: str = "paper_runs/latest") -> dict:
    stage = normalize_stage_name(stage)
    state = PipelineState(run_dir)
    path = state.active_path(stage)
    return {
        "stage": stage,
        "output_path": str(path) if path else None,
        "output": state.read_active_output(stage),
        "state": state.state,
    }

@router.get("/api/download/pdf")
def download_pdf(run_dir: str = "paper_runs/latest"):
    import subprocess
    from fastapi.responses import HTMLResponse

    final_path = Path(run_dir) / "final.md"
    if not final_path.exists():
        raise HTTPException(status_code=404, detail="No paper found. Please run the Paper stage first.")

    result = subprocess.run(
        [
            "pandoc",
            str(final_path),
            "-t", "html5",
            "--standalone",
            "--metadata", "title=Research Paper",
        ],
        capture_output=True,
        text=True,
        env=os.environ,
    )

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"HTML generation failed: {result.stderr}")

    html = result.stdout.replace("</head>", """
<style>
  body {
    max-width: 800px;
    margin: 40px auto;
    padding: 20px 40px;
    font-family: Georgia, serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #000;
  }
  h1 { font-size: 18pt; text-align: center; margin-bottom: 8px; }
  h2 { font-size: 13pt; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 2em; }
  h3 { font-size: 11pt; font-style: italic; }
  p { text-align: justify; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; }
  th, td { border: 1px solid #ccc; padding: 6px 10px; }
  th { background: #f0f0f0; font-weight: bold; }
  @media print {
    body { margin: 0; padding: 2cm; max-width: 100%; }
    h2 { page-break-after: avoid; }
    h3 { page-break-after: avoid; }
    table { page-break-inside: avoid; }
  }
</style>
<script>
  window.onload = function() {
    window.print();
  }
</script>
</head>""")

    return HTMLResponse(content=html)

@router.get("/api/progress")
def get_progress():
    try:
        with open("paper_runs/latest/progress.log", "r") as f:
            return {"lines": f.read().splitlines()}
    except FileNotFoundError:
        return {"lines": []}