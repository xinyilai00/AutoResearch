from config import BASE_URL, API_KEY, AGENT_ID, PRINCIPAL_ID
from citation_verifier import verify_citations

import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DEEP_LITERATURE_SYSTEM_PROMPT = """
You are the Deep Literature Review Agent in an autonomous research pipeline. You will be given a specific research question and a set of academic paper abstracts and metadata retrieved from Semantic Scholar, arXiv, and OpenAlex.

Your job is to conduct a deep, targeted literature review specifically focused on the given research question. You must:

1. Identify the most relevant existing methodologies used to study this question or closely related questions
2. Identify the most relevant datasets that have been used or could be used to investigate this question
3. Summarize the most relevant prior quantitative results and findings directly related to this question
4. Produce a clear statement of exactly what this specific question still needs answered — what is missing, what is contested, and what the next study must do

RULES:
- Stay laser-focused on the specific research question — do not drift into tangential topics
- Only cite papers that were actually provided to you — do NOT hallucinate citations
- Be specific about methodologies, datasets, and quantitative results — avoid vague generalities
- The output will be used by a Proposal Agent to design an experiment, so it must be actionable

OUTPUT in this exact format:

RELEVANT METHODOLOGIES:
- [methodology 1]: [brief description of how it was used and what it found]
- [methodology 2]: [brief description]
...

RELEVANT DATASETS:
- [dataset 1]: [what it contains and why it's relevant]
- [dataset 2]: [what it contains and why it's relevant]
...

PRIOR QUANTITATIVE RESULTS:
- [finding 1]: [specific numbers, effect sizes, or statistical results]
- [finding 2]: [specific numbers, effect sizes, or statistical results]
...

WHAT THIS QUESTION STILL NEEDS:
[2-3 paragraphs clearly stating what remains unanswered, what methodological gaps exist, and what a new study must do to advance knowledge on this specific question]
"""

# ─────────────────────────────────────────────
# ACADEMIC DATABASE SEARCH FUNCTIONS
# ─────────────────────────────────────────────

def search_semantic_scholar(query: str, limit: int = 15) -> list[dict]:
    try:
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "limit": limit,
                "fields": "title,abstract,year,authors,citationCount"
            },
            timeout=10
        )
        data = response.json()
        papers = []
        for p in data.get("data", []):
            if p.get("abstract"):
                papers.append({
                    "title": p.get("title", ""),
                    "abstract": p.get("abstract", ""),
                    "year": p.get("year", ""),
                    "authors": [a["name"] for a in p.get("authors", [])[:3]],
                    "citations": p.get("citationCount", 0),
                    "source": "Semantic Scholar"
                })
        return papers
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return []


def search_arxiv(query: str, limit: int = 15) -> list[dict]:
    try:
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query}",
                "max_results": limit,
                "sortBy": "relevance"
            },
            timeout=60
        )

        if response.status_code != 200:
            print(f"arXiv error: HTTP {response.status_code}")
            return []

        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            print(f"arXiv error: invalid response")
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            abstract = entry.findtext("atom:summary", "", ns).strip()
            if abstract:
                papers.append({
                    "title": entry.findtext("atom:title", "", ns).strip(),
                    "abstract": abstract,
                    "year": entry.findtext("atom:published", "", ns)[:4],
                    "authors": [
                        a.findtext("atom:name", "", ns)
                        for a in entry.findall("atom:author", ns)[:3]
                    ],
                    "citations": None,
                    "source": "arXiv"
                })
        return papers
    except Exception as e:
        print(f"arXiv error: {e}")
        return []


def search_openalex(query: str, limit: int = 15) -> list[dict]:
    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={
                "search": query,
                "per-page": limit,
                "select": "title,abstract_inverted_index,publication_year,authorships,cited_by_count"
            },
            headers={"User-Agent": "AutoResearch/1.0 (research pipeline)"},
            timeout=10
        )
        data = response.json()
        papers = []
        for p in data.get("results", []):
            inv = p.get("abstract_inverted_index")
            if not inv:
                continue
            word_positions = []
            for word, positions in inv.items():
                for pos in positions:
                    word_positions.append((pos, word))
            abstract = " ".join(w for _, w in sorted(word_positions))

            papers.append({
                "title": p.get("title", ""),
                "abstract": abstract,
                "year": p.get("publication_year", ""),
                "authors": [
                    a["author"]["display_name"]
                    for a in p.get("authorships", [])[:3]
                    if a.get("author")
                ],
                "citations": p.get("cited_by_count", 0),
                "source": "OpenAlex"
            })
        return papers
    except Exception as e:
        print(f"OpenAlex error: {e}")
        return []


# ─────────────────────────────────────────────
# SEARCH ORCHESTRATION
# ─────────────────────────────────────────────

def run_deep_searches(research_question: str) -> list[dict]:
    """Run targeted searches based on the specific research question."""
    # Generate focused search queries from the research question
    # Use the question itself + key phrase extractions
    queries = [
        research_question[:200],  # Full question truncated
        " ".join(research_question.split()[:10]),  # First 10 words
        " ".join(research_question.split()[5:15]),  # Middle chunk
    ]

    all_papers = []
    seen_titles = set()

    other_tasks = [
        (source, q)
        for q in queries
        for source in ("semantic_scholar", "openalex")
    ]
    arxiv_tasks = [("arxiv", q) for q in queries]

    def run_search(task):
        source, query = task
        if source == "semantic_scholar":
            return search_semantic_scholar(query, limit=15)
        elif source == "arxiv":
            return search_arxiv(query, limit=15)
        else:
            return search_openalex(query, limit=15)

    def add_papers(results):
        for paper in results:
            title_key = paper["title"].lower().strip()
            if title_key not in seen_titles and paper["abstract"]:
                seen_titles.add(title_key)
                all_papers.append(paper)

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(run_search, task): task for task in other_tasks}
        for future in as_completed(futures):
            add_papers(future.result())

    for task in arxiv_tasks:
        results = run_search(task)
        add_papers(results)
        time.sleep(3)

    print(f"Found {len(all_papers)} unique papers for deep review.")
    return all_papers


# ─────────────────────────────────────────────
# FORMAT PAPERS FOR LLM
# ─────────────────────────────────────────────

def format_papers_for_llm(papers: list[dict], max_papers: int = 30) -> str:
    papers_sorted = sorted(
        papers,
        key=lambda p: (p.get("citations") or 0),
        reverse=True
    )[:max_papers]

    lines = []
    for i, p in enumerate(papers_sorted, 1):
        lines.append(
            f"[{i}] {p['title']} ({p['year']}) — {p['source']}\n"
            f"Authors: {', '.join(p['authors']) if p['authors'] else 'N/A'}\n"
            f"Abstract: {p['abstract'][:400]}...\n"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# DIANJIN API CALLS
# ─────────────────────────────────────────────

def get_response(request_id: str) -> str:
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
                        full_response += data.get("data", {}).get("text", "")
                except:
                    pass
    return full_response


def run_deep_literature_agent(papers_text: str, research_question: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID
    }
    body = {
        "agentId": AGENT_ID,
        "userInput": (
            DEEP_LITERATURE_SYSTEM_PROMPT
            + f"\n\nResearch question: {research_question}"
            + f"\n\nPapers retrieved:\n{papers_text}"
        )
    }
    response = requests.post(
        f"{BASE_URL}/api/agent/run/async",
        headers=headers,
        json=body
    )
    data = response.json()
    request_id = data["data"]["requestId"]
    print("Got requestId:", request_id)
    return get_response(request_id)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run_deep_literature_stage(research_question: str) -> tuple[str, dict]:
    print("\n[Deep Literature Agent] Searching for targeted papers...")
    papers = run_deep_searches(research_question)

    print("\n[Deep Literature Agent] Sending to Dianjin for deep review...")
    papers_text = format_papers_for_llm(papers)
    result = run_deep_literature_agent(papers_text, research_question)

    citation_report = verify_citations(result, research_question)

    return result, citation_report


if __name__ == "__main__":
    sample_question = "Can a machine learning model trained on publicly available wearable sensor data accurately predict next-day athletic performance decrements in individual athletes?"
    result, citation_report = run_deep_literature_stage(sample_question)
    print("\n--- Deep Literature Agent Output ---")
    print(result)
    print(f"\n[Citations] Verified: {len(citation_report['verified'])} | Unverified: {len(citation_report['unverified'])} | Hallucinated: {len(citation_report['hallucinated'])}")