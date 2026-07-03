from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path

try:
    from .experiment_agent import run_experiment_stage
    from .lit_agent_p1 import run_literature_stage
    from .lit_agent_p2 import run_deep_literature_stage
    from .paper_agent import parse_args as parse_paper_args
    from .paper_agent import run_agent as run_paper_agent
    from .pi_agent import run_pi_agent
    from .pipeline_state import PipelineState, generate_hypothesis_from_repo, set_experiment_anchor
    from .proposal_agent import run_proposal_stage
    from .repo_finder_agent import run_repo_finder_agent
    from .repo_grader_agent import run_repo_grader_agent
    from .repo_selector_agent import run_repo_selector_agent
    from .research_question_agent import run_research_question_stage
    from .review_agent import run_review_from_file
except ImportError:
    from experiment_agent import run_experiment_stage
    from lit_agent_p1 import run_literature_stage
    from lit_agent_p2 import run_deep_literature_stage
    from paper_agent import parse_args as parse_paper_args
    from paper_agent import run_agent as run_paper_agent
    from pi_agent import run_pi_agent
    from pipeline_state import PipelineState, generate_hypothesis_from_repo, set_experiment_anchor
    from proposal_agent import run_proposal_stage
    from repo_finder_agent import run_repo_finder_agent
    from repo_grader_agent import run_repo_grader_agent
    from repo_selector_agent import run_repo_selector_agent
    from research_question_agent import run_research_question_stage
    from review_agent import run_review_from_file


def user_selection(questions: list[str]) -> str:
    """Display questions and get user selection."""
    while True:
        print(f"\nEnter a number (1-{len(questions)}) to select a research question, or 'quit' to exit.")
        choice = input("\nYour choice: ").strip().lower()

        if choice == "quit":
            raise SystemExit("Exiting.")

        if choice.isdigit() and 1 <= int(choice) <= len(questions):
            selected = questions[int(choice) - 1]
            print(f"\nYou selected:\n{selected}")
            confirm = input("\nConfirm selection? (yes/no): ").strip().lower()
            if confirm == "yes":
                return selected
            continue

        print(f"Invalid input. Please enter a number between 1 and {len(questions)} or 'quit'.")


def parse_question_list(raw_output: str) -> list[str]:
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        questions = [str(item).strip() for item in parsed if str(item).strip()]
    else:
        questions = [line.strip("- ").strip() for line in raw_output.splitlines() if line.strip()]

    if not questions:
        raise ValueError("Research Question Agent did not return any usable questions.")
    return questions


def persist_selected_repo(state: PipelineState, topic: str, selected_repo: dict) -> str:
    repo_name = selected_repo.get("name") or selected_repo.get("repo")
    repo_url = selected_repo.get("url")
    if not repo_name or not repo_url:
        raise ValueError(f"Selected repo is missing name or URL: {selected_repo}")

    repo_metadata = {"id": repo_name, "name": repo_name, "url": repo_url}
    hypothesis = generate_hypothesis_from_repo(topic, repo_metadata)
    set_experiment_anchor(repo_url, hypothesis, repo_id=repo_name, repo_name=repo_name)

    state.set_metadata("selected_repo_id", repo_name)
    state.set_metadata("selected_repo_name", repo_name)
    state.set_metadata("selected_repo_url", repo_url)
    state.set_metadata("selected_repo_reason", selected_repo.get("reason", ""))
    state.set_metadata("hypothesis", hypothesis)
    return hypothesis


def run_repo_selection(topic: str, state: PipelineState) -> dict:
    print("\n--- Repo Finder Agent ---")
    candidates = run_repo_finder_agent(topic)
    if not candidates:
        raise RuntimeError("Repo Finder returned no candidate repositories.")
    state.set_metadata("repo_candidates", candidates)

    print("\n--- Repo Grader Agent ---")
    token = os.getenv("GITHUB_TOKEN", "")
    graded_repos = []
    max_workers = min(len(candidates), 10)
    print(f"[Repo Grader] Grading {len(candidates)} repos in parallel with {max_workers} worker(s)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_repo_grader_agent, candidate, topic, token): candidate
            for candidate in candidates
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            candidate = futures[future]
            print(f"\n[{index}/{len(candidates)}] {candidate.get('name', 'unknown')}")
            try:
                graded_repos.append(future.result())
            except Exception as exc:
                print(f"[Repo Grader] Skipping {candidate.get('name', 'unknown')} after grading failure: {exc}")

    if not graded_repos:
        raise RuntimeError("Repo Grader returned no usable repository assessments.")
    state.set_metadata("repo_grades", graded_repos)

    print("\n--- Repo Selector Agent ---")
    selected_repo = run_repo_selector_agent(graded_repos, topic)
    if not selected_repo:
        raise RuntimeError("Repo Selector did not choose a repository.")

    hypothesis = persist_selected_repo(state, topic, selected_repo)
    state.write_stage_output(
        "repo_selection",
        json.dumps(
            {
                "selected_repo": selected_repo,
                "hypothesis": hypothesis,
                "graded_repos": graded_repos,
            },
            indent=2,
        ),
    )
    print(f"Selected repo: {selected_repo.get('name')} ({selected_repo.get('url')})")
    print(f"Hypothesis: {hypothesis}")
    return selected_repo


def main():
    topic = input("Enter your research topic: ").strip()
    if not topic:
        raise ValueError("Research topic is required.")

    output_dir = Path("paper_runs/latest")
    state = PipelineState(output_dir)
    state.set_metadata("topic", topic)

    print("\n--- PI Agent ---")
    pi_output = run_pi_agent(topic)
    state.write_stage_output("pi", pi_output)
    print(pi_output)

    print("\n--- Literature Agent (Part 1) ---")
    try:
        lit_output = run_literature_stage(pi_output, topic)
        literature_status = "generated"
    except Exception as exc:
        print(f"Literature failed; using placeholder. Reason: {exc}")
        lit_output = (
            "SUMMARY OF EXISTING WORK:\n"
            "Literature review could not be generated because the external agent API was unavailable.\n\n"
            "GAPS:\n"
            "1. Retry the literature stage when the agent API/network is available.\n"
            "2. Treat downstream research questions as provisional until literature synthesis is regenerated.\n"
        )
        literature_status = "placeholder"
    state.write_stage_output("literature", lit_output, status=literature_status)
    print(lit_output)

    print("\n--- Research Question Agent ---")
    research_questions_output = run_research_question_stage(topic, lit_output)
    state.write_stage_output("research_questions", research_questions_output)
    questions = parse_question_list(research_questions_output)
    print(json.dumps(questions, indent=2))

    if len(questions) == 1:
        selected_question = questions[0]
        print("\nUsing generated research question.")
    else:
        selected_question = user_selection(questions)

    state.write_stage_output("research_question", selected_question)
    print(f"\nSelected research question:\n{selected_question}")

    print("\n--- Proposal Preparation: Deep Literature + Repo Pipeline ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        deep_lit_future = executor.submit(run_deep_literature_stage, selected_question)
        repo_future = executor.submit(run_repo_selection, selected_question, state)

        deep_lit_output = deep_lit_future.result()
        selected_repo = repo_future.result()

    state.write_stage_output("deep_literature", deep_lit_output)
    print("\n--- Deep Literature Agent (Part 2) ---")
    print(deep_lit_output)
    print(f"\nRepo selected for proposal: {selected_repo.get('name')} ({selected_repo.get('url')})")

    print("\n--- Proposal Agent ---")
    proposal_output = run_proposal_stage(selected_question, deep_lit_output, selected_repo=selected_repo)
    state.write_stage_output("proposal", proposal_output)
    print(proposal_output)

    print("\n--- Experiment Agent ---")
    experiment_output = run_experiment_stage(proposal_output, output_dir / "experiment")
    experiment_status = "redesign_needed" if "REDESIGN_NEEDED" in experiment_output else "generated"
    state.write_stage_output("experiment", experiment_output, status=experiment_status)
    print(experiment_output)

    print("\n--- Paper Agent ---")
    paper_args = parse_paper_args(
        [
            "--prompt",
            topic,
            "--pi-output",
            pi_output,
            "--part1-literature",
            lit_output,
            "--research-questions",
            research_questions_output,
            "--research-question",
            selected_question,
            "--deep-literature",
            deep_lit_output,
            "--proposal",
            proposal_output,
            "--experiment",
            experiment_output,
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
    state.set_stage_status("paper", "generated")
    print(f"Draft paper: {final_paper}")

    print("\n--- Review Agent ---")
    try:
        review_dir = run_review_from_file(final_paper, final_dir / "review", rounds=1)
        state.set_stage_status("review", "generated")
        print(f"Reviewed draft: {review_dir / 'reviewed_draft.md'}")
        print(f"Remaining weaknesses: {review_dir / 'remaining_weaknesses.md'}")
    except Exception as exc:
        print(f"Review failed; paper draft is still available. Reason: {exc}")

    print(f"\nDone. Final draft: {final_paper}")


if __name__ == "__main__":
    main()
