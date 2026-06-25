from __future__ import annotations

from pathlib import Path

try:
    from experiment_agent import run_experiment_stage
    from lit_agent_p1 import run_literature_stage
    from lit_agent_p2 import run_deep_literature_stage
    from paper_agent import parse_args as parse_paper_args
    from paper_agent import run_agent as run_paper_agent
    from pi_agent import run_pi_agent
    from pipeline_state import PipelineState, compose_feedback_prompt
    from proposal_agent import run_proposal_stage
    from research_question_agent import run_research_question_stage
    from review_agent import run_review_from_file
except ImportError:
    from backend.experiment_agent import run_experiment_stage
    from backend.lit_agent_p1 import run_literature_stage
    from backend.lit_agent_p2 import run_deep_literature_stage
    from backend.paper_agent import parse_args as parse_paper_args
    from backend.paper_agent import run_agent as run_paper_agent
    from backend.pi_agent import run_pi_agent
    from backend.pipeline_state import PipelineState, compose_feedback_prompt
    from backend.proposal_agent import run_proposal_stage
    from backend.research_question_agent import run_research_question_stage
    from backend.review_agent import run_review_from_file

def apply_stage_feedback(
    stage: str,
    feedback_text: str,
    run_dir: str | Path = "paper_runs/latest",
) -> Path:
    state = PipelineState(run_dir)
    stage = normalize_stage_name(stage)
    state.write_feedback(stage, feedback_text)

    if stage == "pi":
        output = rerun_pi_with_feedback(state, feedback_text)
    elif stage == "literature":
        output = rerun_literature_with_feedback(state, feedback_text)
    elif stage == "deep_literature":
        output = rerun_deep_literature_with_feedback(state, feedback_text)
    elif stage == "research_questions":
        output = rerun_research_questions_with_feedback(state, feedback_text)
    elif stage == "research_question":
        return state.write_stage_output("research_question", feedback_text, status="revised")
    elif stage == "proposal":
        output = rerun_proposal_with_feedback(state, feedback_text)
    elif stage == "experiment":
        output = rerun_experiment_with_feedback(state, feedback_text)
    elif stage == "paper":
        return rerun_paper_with_feedback(state, feedback_text)
    elif stage == "review":
        return rerun_review_with_feedback(state, feedback_text)
    else:
        raise ValueError(f"Feedback is not supported for stage: {stage}")

    return state.write_stage_output(stage, output, status="revised")


def normalize_stage_name(stage: str) -> str:
    aliases = {
        "lit": "literature",
        "literature_part1": "literature",
        "part1_literature": "literature",
        "deep-lit": "deep_literature",
        "deep_lit": "deep_literature",
        "candidate_questions": "research_questions",
        "candidate_research_questions": "research_questions",
        "research-questions": "research_questions",
        "research-question": "research_question",
    }
    key = stage.strip().lower().replace(" ", "_")
    return aliases.get(key, key)


def rerun_pi_with_feedback(state: PipelineState, feedback_text: str) -> str:
    topic = state.get_metadata("topic")
    if not topic:
        raise ValueError("Cannot rerun PI with feedback because run_state.json has no metadata.topic.")
    previous = state.read_active_output("pi")
    revised_topic = compose_feedback_prompt(
        original_input=f"Research topic: {topic}",
        previous_output=previous,
        feedback=feedback_text,
        instruction="Revise the structured PI search query according to the feedback.",
    )
    return run_pi_agent(revised_topic)


def rerun_literature_with_feedback(state: PipelineState, feedback_text: str) -> str:
    topic = state.get_metadata("topic")
    pi_output = state.read_active_output("pi")
    previous = state.read_active_output("literature")
    if not topic or not pi_output:
        raise ValueError("Cannot rerun Literature because topic or PI output is missing.")
    revised_pi_context = compose_feedback_prompt(
        original_input=pi_output,
        previous_output=previous,
        feedback=feedback_text,
        instruction="Revise the literature review and candidate research questions according to the feedback.",
    )
    return run_literature_stage(revised_pi_context, topic)


def rerun_deep_literature_with_feedback(state: PipelineState, feedback_text: str) -> str:
    question = state.read_active_output("research_question")
    previous = state.read_active_output("deep_literature")
    if not question:
        raise ValueError("Cannot rerun Deep Literature because selected research question is missing.")
    revised_question_context = compose_feedback_prompt(
        original_input=question,
        previous_output=previous,
        feedback=feedback_text,
        instruction="Revise the targeted deep literature review according to the feedback.",
    )
    return run_deep_literature_stage(revised_question_context)


def rerun_research_questions_with_feedback(state: PipelineState, feedback_text: str) -> str:
    topic = state.get_metadata("topic")
    literature = state.read_active_output("literature")
    previous = state.read_active_output("research_questions")
    if not topic or not literature:
        raise ValueError("Cannot rerun Research Questions because topic or Literature output is missing.")
    revised_literature_context = compose_feedback_prompt(
        original_input=literature,
        previous_output=previous,
        feedback=feedback_text,
        instruction="Revise the candidate research questions according to the feedback.",
    )
    return run_research_question_stage(topic, revised_literature_context)


def rerun_proposal_with_feedback(state: PipelineState, feedback_text: str) -> str:
    question = state.read_active_output("research_question")
    deep_lit = state.read_active_output("deep_literature")
    previous = state.read_active_output("proposal")
    if not question or not deep_lit:
        raise ValueError("Cannot rerun Proposal because research question or deep literature is missing.")
    revised_deep_lit_context = compose_feedback_prompt(
        original_input=deep_lit,
        previous_output=previous,
        feedback=feedback_text,
        instruction="Revise the experiment proposal according to the feedback while preserving verified public-data constraints.",
    )
    return run_proposal_stage(question, revised_deep_lit_context)


def rerun_experiment_with_feedback(state: PipelineState, feedback_text: str) -> str:
    proposal = state.read_active_output("proposal")
    previous = state.read_active_output("experiment")
    if not proposal:
        raise ValueError("Cannot rerun Experiment because proposal output is missing.")
    revised_proposal_context = compose_feedback_prompt(
        original_input=proposal,
        previous_output=previous,
        feedback=feedback_text,
        instruction=(
            "Revise only the execution instructions needed by the Experiment Agent. "
            "Do not invent results; run the experiment only if the proposal contains an executable dataset spec."
        ),
    )
    return run_experiment_stage(revised_proposal_context, state.run_dir / "experiment")


def rerun_paper_with_feedback(state: PipelineState, feedback_text: str) -> Path:
    topic = state.get_metadata("topic") or "AutoResearch paper"
    previous = state.run_dir / "final.md"
    revised_prompt = (
        f"{topic}\n\n"
        "User feedback for revising the paper draft:\n"
        f"{feedback_text}\n\n"
        "Revise the paper according to the feedback while preserving all verified upstream stage inputs."
    )
    args = parse_paper_args(
        [
            "--prompt",
            revised_prompt,
            "--paper",
            str(previous),
            "--pi-output",
            state.read_active_output("pi"),
            "--part1-literature",
            state.read_active_output("literature"),
            "--research-questions",
            state.read_active_output("research_questions"),
            "--research-question",
            state.read_active_output("research_question"),
            "--deep-literature",
            state.read_active_output("deep_literature"),
            "--proposal",
            state.read_active_output("proposal"),
            "--experiment",
            state.read_active_output("experiment"),
            "--out",
            str(state.run_dir),
            "--iterations",
            "0",
        ]
    )
    output_dir = run_paper_agent(args)
    state.set_stage_status("paper", "revised")
    return output_dir / "final.md"


def rerun_review_with_feedback(state: PipelineState, feedback_text: str) -> Path:
    final_paper = state.run_dir / "final.md"
    if not final_paper.exists():
        raise ValueError("Cannot rerun Review because final.md is missing.")
    state.write_stage_output("review_feedback_context", feedback_text, status="feedback")
    review_dir = run_review_from_file(final_paper, state.run_dir / "review", rounds=1)
    state.set_stage_status("review", "revised")
    return review_dir / "reviewed_draft.md"


if __name__ == "__main__":
    selected_stage = input("Stage to revise: ").strip()
    feedback = input("Feedback: ").strip()
    output_path = apply_stage_feedback(selected_stage, feedback)
    print(f"Revised output: {output_path}")
