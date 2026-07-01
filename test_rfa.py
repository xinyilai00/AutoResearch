from backend.repo_finder_agent import run_repo_finder_agent
from backend.repo_assessor_agent import run_repo_assessor_agent


def main():
    topic = input("Enter a research topic: ").strip()
    if not topic:
        print("No topic entered, exiting.")
        return

    print("\n=== Step 1: Repo Finder ===")
    repos = run_repo_finder_agent(topic)
    if not repos:
        print("Repo finder returned no results.")
        return

    print(f"\nFound {len(repos)} candidate repos. Starting assessment...\n")
    print("\n=== Step 2: Repo Assessor ===")
    selected = run_repo_assessor_agent(repos, topic)

    if not selected:
        print("Repo assessor could not select a repo.")
        return

    print(f"\n=== Selected Repo for: '{topic}' ===\n")
    print(f"Name:        {selected.get('name', '')}")
    print(f"URL:         {selected.get('url', '')}")
    print(f"Description: {selected.get('description', '')}")
    print(f"Reason:      {selected.get('reason', '')}")


if __name__ == "__main__":
    main()