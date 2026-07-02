from pathlib import Path

LOG_PATH = Path("paper_runs/latest/progress.log")

def log(message: str):
    print(message)  # still prints to terminal
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(message + "\n")

def clear():
    if LOG_PATH.exists():
        LOG_PATH.write_text("")