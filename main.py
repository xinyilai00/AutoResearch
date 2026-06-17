from pi_agent import run_pi_agent
from lit_agent_p1 import run_literature_stage

def main():
    topic = input("Enter your research topic: ")
    
    print("\n--- PI Agent ---")
    pi_output = run_pi_agent(topic)

    print("\n--- Literature Agent (Part 1) ---")
    lit_output = run_literature_stage(pi_output, topic)
    print(lit_output)

if __name__ == "__main__":
    main()