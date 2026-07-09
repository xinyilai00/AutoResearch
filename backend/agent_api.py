from __future__ import annotations

import json
import time
from urllib import response

import requests

try:
    from .config import AGENT_ID, API_KEY, BASE_URL, JSON_AGENT_ID, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
except ImportError:
    from config import AGENT_ID, API_KEY, BASE_URL, JSON_AGENT_ID, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API


import json as _json

def log_dianjin_failure(label: str, session_id: str, request_id: str, reason: str) -> None:
    """Append a genuine Dianjin final-failure (after all retries) to a persistent log
    so the supervisor can look up the sessionId in the Dianjin console. Appends across
    all runs; never overwrites."""
    try:
        from pathlib import Path
        from datetime import datetime
        log_path = Path("paper_runs/latest/dianjin_failures.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(
                f"{timestamp} | {label} | FAILED after retries | reason={reason} | "
                f"sessionId={session_id or 'N/A'} | requestId={request_id or 'N/A'}\n"
            )
    except Exception:
        pass

def call_agent_api_json(user_input: str, label: str, max_retries: int = 2, agent_id: int | None = None) -> dict:
    prompt = user_input
    for attempt in range(max_retries + 1):
        response = call_agent_api(prompt, label=label, agent_id=agent_id or JSON_AGENT_ID).strip()
        clean = response.replace("```json", "").replace("```", "").strip()
        try:
            return _json.loads(clean)
        except Exception:
            if attempt < max_retries:
                print(f"[{label}] Response was not valid JSON, retrying with correction...")
                prompt = (
                    user_input
                    + "\n\nYOUR PREVIOUS RESPONSE WAS INVALID. You wrote explanatory text instead of JSON. "
                    + "Your ENTIRE response must be a single valid JSON object. "
                    + "It must start with { and end with }. Nothing before, nothing after. Try again."
                )
            else:
                print(f"[{label}] Failed to get valid JSON after {max_retries + 1} attempts.")
                print(f"[{label}] Last raw response was: {response[:1000]}")
                return {}
    return {}

def call_agent_api(user_input: str, label: str, principal_id: str | None = None, agent_id: int | None = None) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": principal_id or PRINCIPAL_ID,
    }
    body = {"agentId": agent_id or AGENT_ID, "userInput": user_input}
    print(f"[DEBUG] Using agentId: {body['agentId']}")
    if SEND_MODEL_TO_AGENT_API and MODEL:
        body["model"] = MODEL

    last_error: Exception | None = None
    session_id = ""
    request_id = ""
    for attempt in range(1, 4):
        try:
            response = requests.post(
                f"{BASE_URL.rstrip('/')}/api/agent/run/async",
                headers=headers,
                json=body,
                timeout=(60, 300),
            )
            response.raise_for_status()
            request_id = response.json()["data"]["requestId"]
            session_id = response.json()["data"].get("sessionId", "")
            print("Got requestId:", request_id)
            print("Got sessionId:", session_id)
            try:
                from pathlib import Path
                log_path = Path("paper_runs/latest/session_ids.log")
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a") as f:
                    f.write(f"{label}: requestId={request_id}, sessionId={session_id}\n")
            except:
                pass
            return read_agent_stream(request_id, principal_id or PRINCIPAL_ID)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            print(f"{label} API request failed on attempt {attempt}/3: {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)
        except RuntimeError as exc:
            last_error = exc
            print(f"{label} API stream failed on attempt {attempt}/3: {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)
    log_dianjin_failure(label, session_id, request_id, str(last_error))
    raise RuntimeError(f"{label} API unavailable: {last_error}")


def read_agent_stream(request_id: str, principal_id: str) -> str:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": principal_id,
    }
    response = requests.get(
        f"{BASE_URL.rstrip('/')}/api/agent/run/stream",
        headers=headers,
        params={"requestId": request_id},
        stream=True,
        timeout=(60, 300),
    )
    response.encoding = "utf-8"
    response.raise_for_status()

    full = ""
    completed = False
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            data = json.loads(line[5:])
        except json.JSONDecodeError:
            continue

        event_type = data.get("eventType")
        if event_type in {"TEXT_START", "TEXT_DELTA"}:
            full += data.get("data", {}).get("text", "")
        if event_type in {"TEXT_END", "MESSAGE_COMPLETED", "RUN_COMPLETED", "DONE", "COMPLETED"}:
            completed = True
            break  # always break on completion, don't wait for more

    if not full.strip():
        raise RuntimeError(
            "Agent stream ended without returning text."
            + (" (completion event received)" if completed else " (stream closed with no completion event)")
        )
    return full.strip()