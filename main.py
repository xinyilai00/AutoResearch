from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from main import main


if __name__ == "__main__":
    main()
