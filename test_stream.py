import json
import requests

from config import BASE_URL, API_KEY, AGENT_ID, PRINCIPAL_ID

print("RUNNING STREAM TEST")

url = f"{BASE_URL.rstrip('/')}/api/agent/run/async"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
    "X-Principal-Id": PRINCIPAL_ID,
}

body = {
    "agentId": AGENT_ID,
    "userInput": "Say only: hello",
}

response = requests.post(url, headers=headers, json=body, timeout=180)
print("POST status:", response.status_code)
print("POST body:", response.text[:1000])
response.raise_for_status()

request_id = response.json()["data"]["requestId"]
print("requestId:", request_id)

stream_url = f"{BASE_URL.rstrip('/')}/api/agent/run/stream"

stream_headers = {
    "Authorization": f"Bearer {API_KEY}",
    "X-Principal-Id": PRINCIPAL_ID,
}

stream_response = requests.get(
    stream_url,
    headers=stream_headers,
    params={"requestId": request_id},
    stream=True,
    timeout=(30, 300),
)

print("STREAM status:", stream_response.status_code)
print("STREAM body begins below:")
stream_response.raise_for_status()

full = ""

for line in stream_response.iter_lines(decode_unicode=True):
    if not line:
        continue

    print("LINE:", line[:300])

    if not line.startswith("data:"):
        continue

    try:
        data = json.loads(line[5:])
    except json.JSONDecodeError:
        continue

    if data.get("eventType") == "TEXT_DELTA":
        full += data.get("data", {}).get("text", "")

    if data.get("eventType") in {"RUN_COMPLETED", "DONE", "COMPLETED"}:
        break

print("FULL:", full)