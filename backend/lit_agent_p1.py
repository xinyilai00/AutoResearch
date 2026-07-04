try:
    from backend.pipeline_state import get_experiment_anchor
except ImportError:
    from pipeline_state import get_experiment_anchor

try:
    from backend.config import BASE_URL, API_KEY, AGENT_ID, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
    from backend.agent_api import call_agent_api
except ImportError:
    from config import BASE_URL, API_KEY, AGENT_ID, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
    from agent_api import call_agent_api

import requests
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

LITERATURE_SYSTEM_PROMPT = """
You are the Literature Review Agent in an autonomous research pipeline. You will be given a set of academic paper abstracts and metadata retrieved from Semantic Scholar, arXiv, and OpenAlex. 

Your job is to: 
1. Identify the major themes and findings across these papers 
2. Identify clear GAPS in the existing literature, including:
   - Things that have NOT been studied at all
   - Topics that HAVE been studied but not with certain methods, datasets, or analytical approaches
   - Contradictions between papers that need resolution
   - Underexplored angles on well-studied questions

RULES: 
- Do NOT generate candidate research questions. A separate Research Question Agent will do that.
- You MUST follow the output format exactly as specified — do not summarize, do not create tables, do not write to files, do not deviate in any way
- Cite papers using author-year format only, such as (Smith, 2023) or (Smith et al., 2023).
- Do NOT use numeric citation markers such as [1], [22], [2,5], or [3-6].
- DO NOT add any text before SUMMARY OF EXISTING WORK or after the last gap.

OUTPUT — COPY THIS FORMAT EXACTLY, NO DEVIATIONS:

SUMMARY OF EXISTING WORK:
[2-3 paragraph synthesis]

GAPS:
1. [gap 1]
2. [gap 2]
...
"""

# ─────────────────────────────────────────────
# PARSE PI OUTPUT
# ─────────────────────────────────────────────

def parse_pi_output(pi_output: str) -> dict:
    result = {"primary": "", "alternatives": [], "key_terms": []}

    lines = pi_output.strip().splitlines()
    for i, line in enumerate(lines):
        line_clean = line.strip().strip("*`:#")
        if not line_clean:
            continue

        if "alternative queries" in line_clean.lower():
            parts = line_clean.split(":", 1)
            raw = parts[1].strip() if len(parts) > 1 and parts[1].strip() else ""
            if not raw:
                alts = []
                for j in range(i + 1, min(i + 6, len(lines))):
                    alt_line = lines[j].strip().strip("`*")
                    if alt_line and alt_line[0].isdigit():
                        alt_text = alt_line.split(".", 1)[-1].strip().strip("`*")
                        alts.append(alt_text)
                    elif alt_line.startswith("-"):
                        alt_text = alt_line.lstrip("- ").strip().strip("`*")
                        alts.append(alt_text)
                result["alternatives"] = alts
            else:
                result["alternatives"] = [q.strip(" -•`*") for q in raw.split(",") if q.strip()]

        elif "key terms" in line_clean.lower():
            parts = line_clean.split(":", 1)
            if len(parts) > 1:
                result["key_terms"] = [t.strip(" -•`*") for t in parts[1].split(",") if t.strip()]

        elif not result["primary"]:
            if ":" in line_clean:
                result["primary"] = line_clean.split(":", 1)[1].strip().strip("`* ")
            else:
                result["primary"] = line_clean.strip("`*")

    return result

# ─────────────────────────────────────────────
# ACADEMIC DATABASE SEARCH FUNCTIONS
# ─────────────────────────────────────────────

def clean_arxiv_query(query: str, max_words: int = 8) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\s-]", " ", query)
    stopwords = {
        "the", "and", "for", "from", "with", "that", "this",
        "what", "when", "where", "which", "into", "can", "are", "how",
    }
    words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in stopwords]
    return " ".join(words[:max_words])


def search_semantic_scholar(query: str, limit: int = 10) -> list[dict]:
    try:
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": limit, "fields": "title,abstract,year,authors,citationCount,url"},
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
                    "source": "Semantic Scholar",
                    "url": p.get("url", "")
                })
        return papers
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return []


def search_arxiv(query: str, limit: int = 10) -> list[dict]:
    try:
        arxiv_query = clean_arxiv_query(query)
        if not arxiv_query:
            return []
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={"search_query": f"all:{arxiv_query}", "max_results": limit, "sortBy": "relevance"},
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
                    "authors": [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)[:3]],
                    "citations": None,
                    "source": "arXiv",
                    "url": entry.findtext("atom:id", "", ns).strip()
                })
        return papers
    except Exception as e:
        print(f"arXiv error: {e}")
        return []


def search_openalex(query: str, limit: int = 10) -> list[dict]:
    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={"search": query, "per-page": limit, "select": "id,doi,title,abstract_inverted_index,publication_year,authorships,cited_by_count"},
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
                "authors": [a["author"]["display_name"] for a in p.get("authorships", [])[:3] if a.get("author")],
                "citations": p.get("cited_by_count", 0),
                "source": "OpenAlex",
                "url": f"https://doi.org/{p.get('doi')}" if p.get("doi") else p.get("id", "")
            })
        return papers
    except Exception as e:
        print(f"OpenAlex error: {e}")
        return []


# ─────────────────────────────────────────────
# SEARCH ORCHESTRATION
# ─────────────────────────────────────────────

def run_all_searches(parsed: dict) -> list[dict]:
    queries = [parsed["primary"]] + parsed["alternatives"]
    all_papers = []
    seen_titles = set()

    arxiv_tasks = [("arxiv", q) for q in queries]
    other_tasks = [(source, q) for q in queries for source in ("semantic_scholar", "openalex")]

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
            if not paper.get("title"):
                continue
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

    print(f"Found {len(all_papers)} unique papers across all sources.")
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
    papers_sorted = sorted(papers, key=lambda p: (p.get("citations") or 0), reverse=True)[:max_papers]
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


def citation_links_from_papers(papers: list[dict], max_papers: int = 30) -> list[dict]:
    papers_sorted = sorted(papers, key=lambda p: (p.get("citations") or 0), reverse=True)[:max_papers]
    links = []
    for paper in papers_sorted:
        url = str(paper.get("url") or "").strip()
        if not url:
            continue
        links.append({
            "citation": author_year_label(paper),
            "title": str(paper.get("title") or "Untitled"),
            "url": url,
            "source": str(paper.get("source") or "Unknown"),
            "year": paper.get("year") or "",
        })
    return links


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
                labels = [citation_lookup.get(str(i), "citation TODO: author-year needed") for i in range(start, end + 1)]
                return "(" + "; ".join(labels) + ")"
        labels = [citation_lookup.get(n.strip(), "citation TODO: author-year needed") for n in raw_marker.split(",") if n.strip()]
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
            # print(f"DEBUG EVENT: {event_type}")
            if event_type in {"TEXT_START", "TEXT_DELTA"}:
                full_response += data.get("data", {}).get("text", "")
            if event_type in {"TEXT_END", "MESSAGE_COMPLETED", "RUN_COMPLETED", "DONE", "COMPLETED"}:
                if full_response.strip():
                    break
    except requests.exceptions.RequestException:
        if not full_response.strip():
            raise

    # print(f"DEBUG FULL RESPONSE LENGTH: {len(full_response)}")
    return full_response


def run_literature_agent(papers_text: str, topic: str) -> str:
    anchor = get_experiment_anchor()
    anchor_context = f"""
SELECTED BENCHMARK CONTEXT:
- Repository: {anchor.get('repo_name', 'selected repository')}
- Repository URL: {anchor['repo_url']}
- Hypothesis: {anchor['hypothesis']}

You are conducting a literature review to support a benchmark-oriented study using the selected repository. Focus the synthesis and gap analysis on literature directly relevant to the repository's domain, public dataset resources, benchmark workflow, methods, and measurable evaluation metrics. Do not assume the study is about MNIST, CNNs, or PyTorch unless the selected repository context explicitly implies that.
"""
    prompt = (
        anchor_context
        + LITERATURE_SYSTEM_PROMPT
        + f"\n\nResearch topic: {topic}"
        + f"\n\nPapers retrieved:\n{papers_text}"
        + "\n\nIMPORTANT: Begin your response immediately with 'SUMMARY OF EXISTING WORK:'. Do not write any introductory sentences or explain what you are about to do."
    )
    result = call_agent_api(prompt, "Literature")
    return replace_numeric_citation_markers(result, citation_lookup_from_papers_text(papers_text))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run_literature_stage(pi_output: str, original_topic: str, citation_callback=None) -> str:
    print("\n[Literature Agent] Parsing PI output...")
    parsed = parse_pi_output(pi_output)
    print(f"  Primary query: {parsed['primary']}")
    print(f"  Alternatives: {parsed['alternatives']}")

    print("\n[Literature Agent] Searching academic databases...")
    papers = run_all_searches(parsed)

    citation_links = citation_links_from_papers(papers)
    if citation_callback:
        citation_callback(citation_links)

    print("\n[Literature Agent] Sending to Dianjin for gap analysis...")
    papers_text = format_papers_for_llm(papers)
    result = run_literature_agent(papers_text, original_topic)

    return result


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
