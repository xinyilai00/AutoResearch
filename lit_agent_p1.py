from config import BASE_URL, API_KEY, AGENT_ID, PRINCIPAL_ID

import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

LITERATURE_SYSTEM_PROMPT = """
You are the Literature Review Agent in an autonomous research pipeline. You will be given a set of academic paper abstracts and metadata retrieved from Semantic Scholar, arXiv, and OpenAlex. 

Your job is to: 
1. Identify the major themes and findings across these papers 
2. Identify clear GAPS in the existing literature — things that have NOT been studied, contradictions between papers, or underexplored angles 
3. Generate exactly 5-10 candidate research questions that could fill these gaps 


RULES: 
- Each research question must be grounded in the literature (reference specific gaps you found) 
- Questions must be specific and testable/answerable through empirical research 
- Do NOT repeat what has already been researched — focus on what's missing 
- Rank questions from most to least promising 

OUTPUT in this exact format: 

SUMMARY OF EXISTING WORK:
[2-3 paragraph synthesis of major findings and themes]

GAPS: 
- [gap 1] 
- [gap 2] 
... 

CANDIDATE RESEARCH QUESTIONS: 
1. [Most promising question] | Gap addressed: [which gap] 
2. [Question] | Gap addressed: [which gap]
...
"""

# ─────────────────────────────────────────────
# PARSE PI OUTPUT
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# PARSE PI OUTPUT
# ─────────────────────────────────────────────

def parse_pi_output(pi_output: str) -> dict:
    """Extract primary query, alternative queries, and key terms from PI output."""
    result = {"primary": "", "alternatives": [], "key_terms": []}

    for line in pi_output.strip().splitlines():
        line = line.strip()
        if line.lower().startswith("primary search query:"):
            result["primary"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("alternative queries:"):
            raw = line.split(":", 1)[1].strip()
            result["alternatives"] = [q.strip(" -•") for q in raw.split(",") if q.strip()]
        elif line.lower().startswith("key terms:"):
            raw = line.split(":", 1)[1].strip()
            result["key_terms"] = [t.strip(" -•") for t in raw.split(",") if t.strip()]

    return result

# ─────────────────────────────────────────────
# ACADEMIC DATABASE SEARCH FUNCTIONS
# ─────────────────────────────────────────────

def search_semantic_scholar(query: str, limit: int = 10) -> list[dict]:
    """Search Semantic Scholar API."""
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
    
def search_arxiv(query: str, limit: int = 10) -> list[dict]:
    """Search arXiv API."""
    try:
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query}",
                "max_results": limit,
                "sortBy": "relevance"
            },
            timeout=10
        )
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
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

def search_openalex(query: str, limit: int = 10) -> list[dict]:
    """Search OpenAlex API."""
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
            # OpenAlex stores abstracts as inverted index — reconstruct it
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

def run_all_searches(parsed: dict) -> list[dict]:
    """Run searches across all three databases in parallel."""
    queries = [parsed["primary"]] + parsed["alternatives"][:2]  # primary + 2 alts
    all_papers = []
    seen_titles = set()

    search_tasks = []
    for q in queries:
        search_tasks.append(("semantic_scholar", q))
        search_tasks.append(("arxiv", q))
        search_tasks.append(("openalex", q))

    def run_search(task):
        source, query = task
        if source == "semantic_scholar":
            return search_semantic_scholar(query, limit=8)
        elif source == "arxiv":
            return search_arxiv(query, limit=8)
        else:
            return search_openalex(query, limit=8)

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(run_search, task): task for task in search_tasks}
        for future in as_completed(futures):
            for paper in future.result():
                title_key = paper["title"].lower().strip()
                if title_key not in seen_titles and paper["abstract"]:
                    seen_titles.add(title_key)
                    all_papers.append(paper)

    print(f"Found {len(all_papers)} unique papers across all sources.")
    return all_papers

# ─────────────────────────────────────────────
# FORMAT PAPERS FOR LLM
# ─────────────────────────────────────────────

def format_papers_for_llm(papers: list[dict], max_papers: int = 30) -> str:
    """Format paper list into a prompt-friendly string. Cap to avoid token overflow."""
    # Prioritise papers with abstracts and high citations
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

def run_literature_agent(papers_text: str, topic: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID
    }
    body = {
        "agentId": AGENT_ID,
        "userInput": (
            LITERATURE_SYSTEM_PROMPT
            + f"\n\nResearch topic: {topic}"
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

def run_literature_stage(pi_output: str, original_topic: str) -> str:
    print("\n[Literature Agent] Parsing PI output...")
    parsed = parse_pi_output(pi_output)
    print(f"  Primary query: {parsed['primary']}")
    print(f"  Alternatives: {parsed['alternatives']}")

    print("\n[Literature Agent] Searching academic databases...")
    papers = run_all_searches(parsed)

    print("\n[Literature Agent] Sending to Dianjin for gap analysis...")
    papers_text = format_papers_for_llm(papers)
    result = run_literature_agent(papers_text, original_topic)

    return result


# FOR STANDALONE TESTING — paste a PI output directly
if __name__ == "__main__":

    sample_pi_output = """
Primary search query: transformer architecture efficiency neural networks
Alternative queries: efficient transformers, attention mechanism optimization, lightweight transformer models, transformer compression techniques
Key terms: transformer, attention, efficiency, pruning, distillation, quantization, BERT, GPT, inference speed, model compression
"""
    topic = "Making transformers more efficient"
    result = run_literature_stage(sample_pi_output, topic)
    print("\n--- Literature Agent Output ---")
    print(result)