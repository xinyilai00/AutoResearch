from pathlib import Path

from experiment_agent import run_experiment_stage
from paper_agent import parse_args as parse_paper_args
from paper_agent import run_agent as run_paper_agent
from lit_agent_p1 import run_literature_stage
from lit_agent_p2 import run_deep_literature_stage
from pi_agent import run_pi_agent
from pipeline_state import PipelineState
from proposal_agent import run_proposal_stage
from research_question_agent import parse_candidate_research_questions
from research_question_agent import run_research_question_stage
from review_agent import run_review_from_file

def user_selection(questions: list[str]) -> str:
    """Display questions and get user selection."""
    while True:
        print(f"\nEnter a number (1-{len(questions)}) to select a research question, or 'quit' to exit.")

        choice = input("\nYour choice: ").strip().lower()

        if choice == "quit":
            print("Exiting.")
            exit()

        elif choice.isdigit() and 1 <= int(choice) <= len(questions):
            selected = questions[int(choice) - 1]
            print(f"\nYou selected:\n{selected}")
            confirm = input("\nConfirm selection? (yes/no): ").strip().lower()
            if confirm == "yes":
                return selected
            else:
                continue

        else:
            print(f"Invalid input. Please enter a number between 1 and {len(questions)} or 'quit'.")

def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def main():
    topic = input("Enter your research topic: ")
    output_dir = Path("paper_runs/latest")
    stage_dir = output_dir / "stage_outputs"
    stage_dir.mkdir(parents=True, exist_ok=True)
    state = PipelineState(output_dir)
    state.set_metadata("topic", topic)

    # PART 1
    print("\n--- PI Agent ---")
    try:
        pi_output = run_pi_agent(topic)
    except Exception as exc:
        print(f"PI failed; using placeholder. Reason: {exc}")
        pi_output = "PI placeholder: use the raw topic as the provisional search query."
    pi_path = state.write_stage_output("pi", pi_output)

    print("\n--- Literature Agent (Part 1) ---")
    try:
        lit_output = run_literature_stage(pi_output, topic)
    except Exception as exc:
        print(f"Literature failed; using placeholder. Reason: {exc}")
        lit_output = (
            "Literature placeholder: literature review, verified citations, "
            "research gaps, and candidate research questions are pending."
        )
    lit_path = state.write_stage_output("literature", lit_output)
    print(lit_output)

    print("\n--- Research Question Agent ---")
    research_questions_output = run_research_question_stage(topic, lit_path)
    research_questions_path = state.write_stage_output("research_questions", research_questions_output)
    print(research_questions_output)

    questions = parse_candidate_research_questions(research_questions_output)

    if not questions:
        print("\nCould not parse research questions. Paper agent will use a provisional question.")
        selected_question = "No selected research question was parsed; infer a provisional question from the research question output."
    else:
        selected_question = user_selection(questions)
    if "| Gap addressed:" in selected_question:
        selected_question = selected_question.split("| Gap addressed:")[0].strip()
    print(f"\nSelected research question:\n{selected_question}")
    selected_question_path = state.write_stage_output("research_question", selected_question)

    # PART 2
    print("\n--- Deep Literature Agent (Part 2) ---")
    try:
        deep_lit_output = run_deep_literature_stage(selected_question)
        print(deep_lit_output)
        deep_lit_path = state.write_stage_output("deep_literature", deep_lit_output)
    except Exception as exc:
        print(f"Deep literature failed; using placeholder. Reason: {exc}")
        deep_lit_path = state.write_stage_output("deep_literature", "Deep literature placeholder.", status="placeholder")

    print("\n--- Proposal Agent ---")
    proposal_output = run_proposal_stage(selected_question, deep_lit_path)
    proposal_path = state.write_stage_output("proposal", proposal_output)
    print(proposal_output)
    
    print("\n--- Experiment Agent ---")
    experiment_output = run_experiment_stage(proposal_path, output_dir / "experiment")
    experiment_status = "redesign_needed" if "REDESIGN_NEEDED" in experiment_output else "generated"
    experiment_path = state.write_stage_output("experiment", experiment_output, status=experiment_status)
    print(experiment_output)
    return
    print("\n--- Paper Agent ---")
    paper_args = parse_paper_args(
        [
            "--prompt",
            topic,
            "--pi-output",
            str(pi_path),
            "--part1-literature",
            str(lit_path),
            "--research-questions",
            str(research_questions_path),
            "--research-question",
            str(selected_question_path),
            "--deep-literature",
            str(deep_lit_path),
            "--proposal",
            str(proposal_path),
            "--experiment",
            str(experiment_path),
            "--out",
            str(output_dir),
            "--iterations",
            "0",
            "--max-tokens",
            "14000",
        ]
    )
    final_dir = run_paper_agent(paper_args)
    final_paper = final_dir / "final.md"
    print(f"Draft paper: {final_paper}")

    print("\n--- Review Agent ---")
    try:
        review_dir = run_review_from_file(final_paper, final_dir / "review", rounds=1)
        print(f"Reviewed draft: {review_dir / 'reviewed_draft.md'}")
        print(f"Remaining weaknesses: {review_dir / 'remaining_weaknesses.md'}")
    except Exception as exc:
        print(f"Review failed; paper draft is still available. Reason: {exc}")

    print(f"\nDone. Final draft: {final_paper}")

if __name__ == "__main__":
    main()
