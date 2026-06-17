from config import BASE_URL, API_KEY, AGENT_ID, PRINCIPAL_ID

import requests
import json


# PI System Prompt
PI_SYSTEM_PROMPT = """
You are the PI (Principal Investigator) of an autonomous research pipeline. Your only job is to take a raw research topic provided by the user and convert it into a clean, structured search query that can be used to search academic databases like Semantic Scholar, arXiv, and OpenAlex. Your output will be used as the input for an LLM that does a literature review.

RULES:
- The query should be specific enough to return relevant academic papers
- The query should be comprehensive enough to cover the full landscape of the research topic
- Your output should include a primary search query and 3-4 alternative queries
- If the topic is too vague, only output a clarifying question
- DO NOT formulate a research question or hypothesis
- Your output will be passed directly to a literature search engine
- DO NOT use any markdown formatting, bold, italics, or special characters
- Output plain text only

IMPORTANT: You MUST begin your response with exactly "Primary search query:" followed by the query. This is required.

OUTPUT in this exact format: (copy exactly, no extra characters, no markdown, no bold)
- Primary search query: [main search string]
- Alternative queries: [3-4 variations using different terminology]
- Key terms: [5-10 individual keywords relevant to this topic]
"""

def get_response(request_id):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID
    }

    response = requests.get(
        f"{BASE_URL}/api/agent/run/stream",
        headers=headers,
        params={"requestId": request_id},
        stream=True
    )

    full_response = ""

    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data:"):
                try:
                    data = json.loads(decoded[5:])
                    if data.get("eventType") == "TEXT_DELTA":
                        text = data.get("data", {}).get("text", "")
                        full_response += text
                except:
                    pass

    print(full_response)
    return full_response

def run_pi_agent(user_topic):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID
    }

    body = {
        "agentId": AGENT_ID,
        "userInput": PI_SYSTEM_PROMPT + "\n\nResearch topic: " + user_topic
    }

    response = requests.post(
        f"{BASE_URL}/api/agent/run/async",
        headers=headers,
        json=body
    )

    data = response.json()
    request_id = data["data"]["requestId"]
    print("Got requestId:", request_id)
    
    print("\n--- Agent Response ---")
    return get_response(request_id)


if __name__ == "__main__":
    # create_principal()  # already done, don't run again
    user_topic = input("Enter your research topic: ")
    run_pi_agent(user_topic)