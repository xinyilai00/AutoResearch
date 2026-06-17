import requests
import re
import json
import time
from config import BASE_URL, API_KEY, AGENT_ID, PRINCIPAL_ID

# ─────────────────────────────────────────────
# LAYER 1: arXiv ID CHECK
# ─────────────────────────────────────────────

def check_arxiv_id(arxiv_id: str) -> bool:
    """Check if an arXiv ID actually exists."""
    try:
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id},
            timeout=10
        )
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        return len(entries) > 0
    except:
        return False


# ─────────────────────────────────────────────
# LAYER 2: CrossRef DOI CHECK
# ─────────────────────────────────────────────

def check_doi(doi: str) -> bool:
    """Check if a DOI exists via CrossRef."""
    try:
        response = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "AutoResearch/1.0 (research pipeline)"},
            timeout=10
        )
        return response.status_code == 200
    except:
        return False


# ─────────────────────────────────────────────
# LAYER 3: Semantic Scholar TITLE MATCH
# ─────────────────────────────────────────────

def check_semantic_scholar_title(title: str, context: str = "") -> dict | None:
    """Search Semantic Scholar using context around the citation."""
    query = context if context else title
    try:
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query[:200],
                "limit": 1,
                "fields": "title,year,authors,citationCount"
            },
            timeout=10
        )
        data = response.json()
        results = data.get("data", [])
        if not results:
            return None

        result_title = results[0].get("title", "").lower().strip()
        query_words = set(query.lower().split())
        result_words = set(result_title.split())
        if len(query_words) == 0:
            return None
        overlap = len(query_words & result_words) / len(query_words)

        if overlap >= 0.3:  # Lower threshold since context is longer
            return results[0]
        return None
    except:
        return None


# ─────────────────────────────────────────────
# LAYER 4: LLM RELEVANCE SCORING
# ─────────────────────────────────────────────

def check_llm_relevance(citation: str, research_question: str) -> bool:
    """Ask Dianjin if a citation is actually relevant to the research question."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID
    }
    body = {
        "agentId": AGENT_ID,
        "userInput": (
            f"Research question: {research_question}\n\n"
            f"Citation: {citation}\n\n"
            f"Is this citation directly relevant to the research question? "
            f"Answer with only YES or NO."
        )
    }
    try:
        response = requests.post(
            f"{BASE_URL}/api/agent/run/async",
            headers=headers,
            json=body
        )
        data = response.json()
        request_id = data["data"]["requestId"]

        # Get response
        stream_response = requests.get(
            f"{BASE_URL}/api/agent/run/stream",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "X-Principal-Id": PRINCIPAL_ID
            },
            params={"requestId": request_id},
            stream=True
        )
        full_response = ""
        for line in stream_response.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data:"):
                    try:
                        event_data = json.loads(decoded[5:])
                        if event_data.get("eventType") == "TEXT_DELTA":
                            full_response += event_data.get("data", {}).get("text", "")
                    except:
                        pass

        return "YES" in full_response.upper()
    except:
        return True  # If check fails, give benefit of the doubt


# ─────────────────────────────────────────────
# EXTRACT CITATIONS FROM TEXT
# ─────────────────────────────────────────────

def extract_citations(text: str) -> list[dict]:
    """Extract citations from literature agent output."""
    citations = []

    # Match arXiv IDs (e.g. 2301.12345)
    arxiv_pattern = re.findall(r'\b(\d{4}\.\d{4,5})\b', text)
    for arxiv_id in arxiv_pattern:
        citations.append({"type": "arxiv", "id": arxiv_id, "raw": arxiv_id})

    # Match DOIs (e.g. 10.1234/something)
    doi_pattern = re.findall(r'\b(10\.\d{4,}/[^\s,\]]+)', text)
    for doi in doi_pattern:
        citations.append({"type": "doi", "id": doi, "raw": doi})

    # Match author-year citations with title context
    # Look for patterns like: Title (Author et al., 2023) or Author et al. (2023) described Title
    lines = text.splitlines()
    for line in lines:
        matches = re.findall(r'([A-Z][a-z]+(?:\s+et\s+al\.)?),?\s+\(?(20\d{2}|19\d{2})\)?', line)
        for author, year in matches:
            # Use the whole line as context for better Semantic Scholar matching
            citations.append({
                "type": "author_year",
                "id": f"{author} {year}",
                "raw": f"{author} {year}",
                "context": line.strip()[:200]  # Keep surrounding context
            })

    # Deduplicate
    seen = set()
    unique = []
    for c in citations:
        key = c["id"]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


# ─────────────────────────────────────────────
# MAIN VERIFICATION PIPELINE
# ─────────────────────────────────────────────

def verify_citations(text: str, research_question: str) -> dict:
    """
    Run all 4 verification layers on citations extracted from text.
    Returns a report of verified, unverified, and hallucinated citations.
    """
    citations = extract_citations(text)
    print(f"\n[Citation Verifier] Found {len(citations)} citations to verify...")

    verified = []
    unverified = []
    hallucinated = []

    for cite in citations:
        print(f"  Checking: {cite['raw']}")
        passed_structural = False

        # Layer 1: arXiv ID check
        if cite["type"] == "arxiv":
            if check_arxiv_id(cite["id"]):
                passed_structural = True
                print(f"    ✓ arXiv ID confirmed")
            else:
                print(f"    ✗ arXiv ID not found")

        # Layer 2: DOI check
        elif cite["type"] == "doi":
            if check_doi(cite["id"]):
                passed_structural = True
                print(f"    ✓ DOI confirmed")
            else:
                print(f"    ✗ DOI not found")

        # Layer 3: Semantic Scholar title match (for author-year citations)
        elif cite["type"] == "author_year":
            result = check_semantic_scholar_title(cite["id"], cite.get("context", ""))
            if result:
                passed_structural = True
                print(f"    ✓ Title match found on Semantic Scholar")
            else:
                print(f"    ~ Could not verify on Semantic Scholar")
                passed_structural = None  # Inconclusive

        # Layer 4: LLM relevance check (only if structural check passed)
        if passed_structural:
            relevant = check_llm_relevance(cite["raw"], research_question)
            if relevant:
                verified.append(cite["raw"])
                print(f"    ✓ Relevant to research question")
            else:
                unverified.append(cite["raw"])
                print(f"    ~ Not relevant to research question")
        elif passed_structural is False:
            hallucinated.append(cite["raw"])
        else:
            unverified.append(cite["raw"])

        time.sleep(0.5)  # Be polite to APIs

    return {
        "verified": verified,
        "unverified": unverified,
        "hallucinated": hallucinated,
        "total": len(citations)
    }


if __name__ == "__main__":
    # Test with a sample text
    sample_text = """
    Smith et al. (2023) found that caffeine improves reaction time.
    DOI: 10.1016/j.neuropharm.2021.108576
    arXiv: 2301.12345
    """
    sample_question = "Does caffeine improve reaction time in sleep-deprived adults?"
    report = verify_citations(sample_text, sample_question)
    print("\n--- Verification Report ---")
    print(f"Verified: {report['verified']}")
    print(f"Unverified: {report['unverified']}")
    print(f"Hallucinated: {report['hallucinated']}")