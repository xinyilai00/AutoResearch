from pi_agent import run_pi_agent
from lit_agent_p1 import run_literature_stage

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

def main():
    topic = input("Enter your research topic: ")

    # PART 1
    print("\n--- PI Agent ---")
    pi_output = run_pi_agent(topic)

    print("\n--- Literature Agent (Part 1) ---")
    lit_output = run_literature_stage(pi_output, topic)
    print(lit_output)

    questions = parse_research_questions(lit_output)

    if not questions:
        print("\nCould not parse research questions. Please check the output above.")
        exit()

    selected_question = user_selection(questions)
    if "| Gap addressed:" in selected_question:
        selected_question = selected_question.split("| Gap addressed:")[0].strip()
    print(f"\nSelected research question:\n{selected_question}")
    # PART 2 goes here

if __name__ == "__main__":
    main()