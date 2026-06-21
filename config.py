import os
from dotenv import load_dotenv

from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
AGENT_ID = os.getenv("AGENT_ID")
PRINCIPAL_ID = os.getenv("PRINCIPAL_ID")
MODEL = os.getenv("MODEL") or "Qwen3.7-Max"
SEND_MODEL_TO_AGENT_API = os.getenv("SEND_MODEL_TO_AGENT_API", "").lower() == "true"
