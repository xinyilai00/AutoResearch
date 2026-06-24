from __future__ import annotations

import json
import time

import requests

try:
    from .config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
except ImportError:
    from config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API


def call_agent_api(user_input: str, label: str, principal_id: str | None = None) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": principal_id or PRINCIPAL_ID,
    }
    body = {"agentId": AGENT_ID, "userInput": user_input}
    if SEND_MODEL_TO_AGENT_API and MODEL:
        body["model"] = MODEL

    last_error: Exception | None = None
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
            print("Got requestId:", request_id)
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
            if full.strip():
                break

    if not full.strip():
        raise RuntimeError("Agent stream ended without returning text.")
    return full.strip()
