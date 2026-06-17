from pathlib import Path

from paper_agent import parse_args as parse_paper_args
from paper_agent import run_agent as run_paper_agent
from lit_agent_p1 import run_literature_stage
from pi_agent import run_pi_agent
from review_agent import run_review_from_file
from lit_agent_p2 import run_deep_literature_stage

def parse_research_questions(lit_output: str) -> list[str]:
    questions = []
    in_questions_section = False
    
    for line in lit_output.splitlines():
        line = line.strip()
        
        if "CANDIDATE RESEARCH QUESTIONS" in line.upper():
            in_questions_section = True
            continue
        
        if in_questions_section and line and line[0].isdigit() and (". " in line or ") " in line):
            if ". " in line:
                q = line.split(". ", 1)[1].strip()
            else:
                q = line.split(") ", 1)[1].strip()
            if len(q) > 30:
                questions.append(q)
    
    return questions

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

    # PART 1
    print("\n--- PI Agent ---")
    try:
        pi_output = run_pi_agent(topic)
    except Exception as exc:
        print(f"PI failed; using placeholder. Reason: {exc}")
        pi_output = "PI placeholder: use the raw topic as the provisional search query."
    pi_path = write_text(stage_dir / "pi_output.md", pi_output)

    print("\n--- Literature Agent (Part 1) ---")
    try:
        lit_output = run_literature_stage(pi_output, topic)
    except Exception as exc:
        print(f"Literature failed; using placeholder. Reason: {exc}")
        lit_output = (
            "Literature placeholder: literature review, verified citations, "
            "research gaps, and candidate research questions are pending."
        )
    lit_path = write_text(stage_dir / "literature_output.md", lit_output)
    print(lit_output)

    questions = parse_research_questions(lit_output)

    if not questions:
        print("\nCould not parse research questions. Paper agent will use a provisional question.")
        selected_question = "No selected research question was parsed; infer a provisional question from the literature output."
    else:
        selected_question = user_selection(questions)
    if "| Gap addressed:" in selected_question:
        selected_question = selected_question.split("| Gap addressed:")[0].strip()
    print(f"\nSelected research question:\n{selected_question}")
    selected_question_path = write_text(stage_dir / "selected_question.md", selected_question)

    proposal_path = write_text(
        stage_dir / "proposal_output.md",
        "Proposal placeholder: hypothesis, variables, experiment design, and success criteria are pending.",
    )
    experiment_path = write_text(
        stage_dir / "experiment_output.md",
        "Experiment placeholder: experiment execution and results are pending. Do not report completed findings.",
    )

    # PART 2
    print("\n--- Paper Agent ---")
    paper_args = parse_paper_args(
        [
            "--prompt",
            topic,
            "--pi-output",
            str(pi_path),
            "--part1-literature",
            str(lit_path),
            "--research-question",
            str(selected_question_path),
            "--proposal",
            str(proposal_path),
            "--experiment",
            str(experiment_path),
            "--out",
            str(output_dir),
            "--iterations",
            "0",
            "--max-tokens",
            "3000",
        ]
    )
    final_dir = run_paper_agent(paper_args)
    final_paper = final_dir / "final.md"
    print(f"Draft paper: {final_paper}")

    print("\n--- Review Agent ---")
    try:
        run_review_from_file(final_paper, final_dir / "review")
        print(f"Reviewed draft: {final_dir / 'review' / 'reviewed_draft.md'}")
        print(f"Identified weaknesses: {final_dir / 'review' / 'identified_weaknesses.md'}")
    except Exception as exc:
        print(f"Review failed; paper draft is still available. Reason: {exc}")

    print(f"\nDone. Final draft: {final_paper}")
    print("\n--- Deep Literature Agent (Part 2) ---")
    deep_lit_output, citation_report = run_deep_literature_stage(selected_question)
    print(deep_lit_output)
    print(f"\n[Citations] Verified: {len(citation_report['verified'])} | Unverified: {len(citation_report['unverified'])} | Hallucinated: {len(citation_report['hallucinated'])}")
    # Proposal agent goes here

    

if __name__ == "__main__":
    main()
