from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.feedback import apply_stage_feedback, normalize_stage_name
from backend.experiment_agent import run_experiment_stage
from backend.lit_agent_p1 import run_literature_stage
from backend.lit_agent_p2 import run_deep_literature_stage
from backend.paper_agent import parse_args as parse_paper_args
from backend.paper_agent import run_agent as run_paper_agent
from backend.pi_agent import run_pi_agent
from backend.pipeline_state import PipelineState
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


class StageFeedbackRequest(BaseModel):
    feedback: str
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
        "output": read_output(path),
        "state": state.state,
    }


@router.post("/api/stages/{stage}/run")
def run_stage(stage: str, request: StageRunRequest) -> dict:
    print(f"DEBUG: received stage = {stage}")
    stage = normalize_stage_name(stage)
    print(f"DEBUG: normalized stage = {stage}")
    state = PipelineState(request.run_dir)
    if request.topic:
        state.set_metadata("topic", request.topic)

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
        output = run_literature_stage(pi_output, topic)
        return state.write_stage_output("literature", output)

    if stage == "research_questions":
        topic = request.topic or state.get_metadata("topic")
        literature = request.literature or state.read_active_output("literature")
        if not topic or not literature:
            raise ValueError("Research Questions stage requires topic and literature output.")
        output = run_research_question_stage(topic, literature)
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
        output = run_deep_literature_stage(question)
        return state.write_stage_output("deep_literature", output)

    if stage == "proposal":
        question = request.research_question or state.read_active_output("research_question")
        deep_literature = request.deep_literature or state.read_active_output("deep_literature")
        if not question or not deep_literature:
            raise ValueError("Proposal stage requires research_question and deep_literature.")
        output = run_proposal_stage(question, deep_literature)
        return state.write_stage_output("proposal", output)

    if stage == "experiment":
        proposal = request.proposal or state.read_active_output("proposal")
        if not proposal:
            raise ValueError("Experiment stage requires proposal output.")
        output = run_experiment_stage(proposal, state.run_dir / "experiment")
        status = "redesign_needed" if "REDESIGN_NEEDED" in output else "generated"
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
        "--prompt",
        topic,
        "--pi-output",
        str(state.active_path("pi") or ""),
        "--part1-literature",
        str(state.active_path("literature") or ""),
        "--research-questions",
        str(state.active_path("research_questions") or ""),
        "--research-question",
        str(state.active_path("research_question") or ""),
        "--deep-literature",
        str(state.active_path("deep_literature") or ""),
        "--proposal",
        str(state.active_path("proposal") or ""),
        "--experiment",
        str(state.active_path("experiment") or ""),
        "--out",
        str(state.run_dir),
        "--iterations",
        "0",
        "--max-tokens",
        "14000",
    ]
    if paper_seed:
        args_list.extend(["--paper", paper_seed])

    output_dir = run_paper_agent(parse_paper_args(args_list))
    final_path = output_dir / "final.md"
    state.set_stage_status("paper", "generated")
    return final_path


def run_review_stage(request: StageRunRequest, state: PipelineState) -> Path:
    draft_path = Path(request.paper) if request.paper else state.run_dir / "final.md"
    if not draft_path.exists():
        raise ValueError("Review stage requires an existing paper draft.")
    review_dir = run_review_from_file(draft_path, state.run_dir / "review", rounds=1)
    state.set_stage_status("review", "generated")
    return review_dir / "reviewed_draft.md"


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
