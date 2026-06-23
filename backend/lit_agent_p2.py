try:
    from .config import BASE_URL, API_KEY, AGENT_ID, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
except ImportError:
    from config import BASE_URL, API_KEY, AGENT_ID, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API

import requests
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DEEP_LITERATURE_SYSTEM_PROMPT = """
You are the Deep Literature Review Agent in an autonomous research pipeline. You will be given a specific research question and a set of academic paper abstracts and metadata retrieved from Semantic Scholar, arXiv, and OpenAlex.

CRITICAL: Do NOT use any tools. Do NOT write to any files. Do NOT summarize your output. Return your ENTIRE response as plain text directly in this message following the exact output format below. Do not deviate from this format under any circumstances.

Your job is to conduct a deep, targeted literature review specifically focused on the given research question. You must:

1. Identify the most relevant existing methodologies used to study this question or closely related questions
2. Identify the most relevant datasets that have been used or could be used to investigate this question
3. Summarize the most relevant prior quantitative results and findings directly related to this question
4. Produce a clear statement of exactly what this specific question still needs answered — what is missing, what is contested, and what the next study must do

RULES:
- Stay laser-focused on the specific research question — do not drift into tangential topics
- Only cite papers that were actually provided to you — do NOT hallucinate citations
- Cite papers using author-year format only, such as (Smith, 2023) or (Smith et al., 2023)
- Do NOT use numeric citation markers such as [1], [22], [2,5], or [3-6]
- Be specific about methodologies, datasets, and quantitative results — avoid vague generalities
- The output will be used by a Proposal Agent to design an experiment, so it must be actionable
- Return ALL content directly as text in your response — do not use file writing tools or any other tools
- Do not provide a summary — provide the FULL structured output in the exact format specified below

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

def clean_arxiv_query(query: str, max_words: int = 8) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\s-]", " ", query)
    stopwords = {
        "the",
        "and",
        "for",
        "from",
        "with",
        "that",
        "this",
        "what",
        "when",
        "where",
        "which",
        "into",
        "can",
        "are",
        "how",
    }
    words = [
        word
        for word in cleaned.split()
        if len(word) > 2 and word.lower() not in stopwords
    ]
    return " ".join(words[:max_words])


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
        arxiv_query = clean_arxiv_query(query)
        if not arxiv_query:
            return []

        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{arxiv_query}",
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

def author_year_label(paper: dict) -> str:
    authors = paper.get("authors") or []
    year = str(paper.get("year") or "n.d.").strip() or "n.d."
    title = str(paper.get("title") or "Unknown").strip()

    if not authors:
        lead = " ".join(title.split()[:3]) or "Unknown"
        return f"{lead}, {year}"

    first_author = str(authors[0]).strip()
    first_surname = first_author.split()[-1] if first_author.split() else first_author
    if len(authors) == 1:
        return f"{first_surname}, {year}"
    if len(authors) == 2:
        second_author = str(authors[1]).strip()
        second_surname = second_author.split()[-1] if second_author.split() else second_author
        return f"{first_surname} & {second_surname}, {year}"
    return f"{first_surname} et al., {year}"


def format_papers_for_llm(papers: list[dict], max_papers: int = 30) -> str:
    papers_sorted = sorted(
        papers,
        key=lambda p: (p.get("citations") or 0),
        reverse=True
    )[:max_papers]

    lines = []
    for p in papers_sorted:
        citation_key = author_year_label(p)
        lines.append(
            f"Citation: ({citation_key})\n"
            f"Title: {p['title']} ({p['year']}) — {p['source']}\n"
            f"Authors: {', '.join(p['authors']) if p['authors'] else 'N/A'}\n"
            f"Abstract: {p['abstract'][:400]}...\n"
        )
    return "\n".join(lines)


def citation_lookup_from_papers_text(papers_text: str) -> dict[str, str]:
    lookup = {}
    citation_index = 1
    for line in papers_text.splitlines():
        match = re.match(r"^Citation:\s*\((.+)\)\s*$", line.strip())
        if match:
            lookup[str(citation_index)] = match.group(1).strip()
            citation_index += 1
    return lookup


def replace_numeric_citation_markers(text: str, citation_lookup: dict[str, str]) -> str:
    def replacement(match: re.Match) -> str:
        raw_marker = match.group(1).strip()
        if "-" in raw_marker:
            bounds = [part.strip() for part in raw_marker.split("-", 1)]
            if all(part.isdigit() for part in bounds):
                start, end = int(bounds[0]), int(bounds[1])
                labels = [
                    citation_lookup.get(str(index), "citation TODO: author-year needed")
                    for index in range(start, end + 1)
                ]
                return "(" + "; ".join(labels) + ")"

        labels = [
            citation_lookup.get(number.strip(), "citation TODO: author-year needed")
            for number in raw_marker.split(",")
            if number.strip()
        ]
        return "(" + "; ".join(labels) + ")"

    return re.sub(r"\[(\d+(?:\s*,\s*\d+)*|\d+\s*-\s*\d+)\]", replacement, text)


# ─────────────────────────────────────────────
# DIANJIN API CALLS
# ─────────────────────────────────────────────

def get_response(request_id: str) -> str:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID
    }
    full_response = ""
    response = requests.get(
        f"{BASE_URL}/api/agent/run/stream",
        headers=headers,
        params={"requestId": request_id},
        stream=True,
        timeout=(30, 300),
    )
    response.encoding = "utf-8"
    response.raise_for_status()

    try:
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:])
            except json.JSONDecodeError:
                continue

            event_type = data.get("eventType")
            if event_type in {"TEXT_START", "TEXT_DELTA"}:
                full_response += data.get("data", {}).get("text", "")
            if event_type in {"TEXT_END", "MESSAGE_COMPLETED", "RUN_COMPLETED", "DONE", "COMPLETED"}:
                if full_response.strip():
                    break
    except requests.exceptions.RequestException:
        if not full_response.strip():
            raise
    
    for i in range(1, len("RELEVANT METHODOLOGIES")):
        if full_response.startswith("RELEVANT METHODOLOGIES"[i:]):
            full_response = "RELEVANT METHODOLOGIES"[:i] + full_response
            break

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
    
    if SEND_MODEL_TO_AGENT_API and MODEL:
        body["model"] = MODEL

    response = requests.post(
        f"{BASE_URL}/api/agent/run/async",
        headers=headers,
        json=body
    )
    data = response.json()
    request_id = data["data"]["requestId"]
    print("Got requestId:", request_id)
    result = get_response(request_id)
    return replace_numeric_citation_markers(result, citation_lookup_from_papers_text(papers_text))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run_deep_literature_stage(research_question: str) -> str:
    print("\n[Deep Literature Agent] Searching for targeted papers...")
    papers = run_deep_searches(research_question)

    print("\n[Deep Literature Agent] Sending to Dianjin for deep review...")
    papers_text = format_papers_for_llm(papers)
    result = run_deep_literature_agent(papers_text, research_question)

    return result


if __name__ == "__main__":
    sample_question = "Can a machine learning model trained on publicly available wearable sensor data accurately predict next-day athletic performance decrements in individual athletes?"
    result = run_deep_literature_stage(sample_question)
    print("\n--- Deep Literature Agent Output ---")
    print(result)