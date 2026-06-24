from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

try:
    from .config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API
except ImportError:
    from config import AGENT_ID, API_KEY, BASE_URL, MODEL, PRINCIPAL_ID, SEND_MODEL_TO_AGENT_API


PROPOSAL_SYSTEM_PROMPT = """
You are the Proposal Agent in an autonomous research pipeline.

Input:
- A selected research question
- A deep literature review from previous stages

Job:
Present an executable data analysis design based on existing literature and provide a hypothesis for the research question.

Critical rules:
- The data analysis CANNOT be fake.
- The data analysis must be possible to implement using only public data, prior-work datasets, or data obtainable from public databases/repositories such as arXiv, Semantic Scholar, OpenAlex, Kaggle, Hugging Face Datasets, UCI, Papers With Code, PubMed, Crossref, GitHub, or other legitimate public sources.
- Treat the word "experiment" as an executable data analysis experiment. Do not propose a lab experiment, clinical study, human-subject intervention, wet-lab procedure, survey collection, physical sensor deployment, or any design that requires collecting new private data.
- The Experiment Agent can only run analysis over databases/files it can load. Therefore the proposal must define data sources, variables, preprocessing, modeling/statistical analysis, baselines, metrics, validation splits, and success criteria.
- If the real answer would require new data collection or a non-data-analysis procedure, state that clearly and set runner_type to NEEDS_NEW_RUNNER.
- Do not claim that a dataset exists unless it is named in the deep literature review, listed in the public dataset search results, or clearly marked as TO_VERIFY.
- Do not fabricate citations, dataset sizes, URLs, metrics, baselines, or prior results.
- If you cite or refer to prior work, use author-year format only, such as (Smith, 2023).
- Do NOT use or preserve numeric citation markers such as [1], [22], [2,5], or [3-6].
- If a required dataset is not confirmed in the provided deep literature review, label it as TO_VERIFY and explain how the Experiment stage should verify it.
- If a GitHub, Hugging Face, or UCI result is used, label it with its source status and explain that the Experiment stage must verify license, data files, documentation quality, schema, and reproducibility before execution.
- The proposal must be implementable by a later Experiment Agent using code and downloaded/public data.
- The proposal must include a machine-readable EXPERIMENT EXECUTION SPEC so the Experiment Agent knows exactly what to download/load, what target column to use, what task type to run, and what metric determines success.
- Prefer analyses that can be run with reasonable compute and reproducible data.
- Do not execute the analysis.
- Do not write code.
- Return plain text only.

Output in this exact format:

RESEARCH QUESTION:
[selected research question]

HYPOTHESIS:
[one testable hypothesis]

EXPERIMENT DESIGN:
[specific executable data analysis design based on public/prior-work datasets; do not propose a lab experiment, human-subject study, wet-lab procedure, or non-executable intervention]

PUBLIC DATA SOURCES:
- [dataset/source 1]: [what it contains, why it is relevant, whether it is CONFIRMED_FROM_LITERATURE or TO_VERIFY]
- [dataset/source 2]: [same]

DATA COLLECTION PLAN:
[how the Experiment Agent should retrieve or construct the dataset from public sources]

METHODOLOGY:
[data preprocessing, variables, models or statistical methods, baselines, validation scheme, and evaluation metrics]

KEY VARIABLES:
- Independent variables: [...]
- Dependent variables: [...]
- Control variables: [...]

SUCCESS CRITERIA:
- [criterion 1]
- [criterion 2]
- [criterion 3]

FEASIBILITY CHECK:
[why this can be implemented with public/prior-work data only, or what must be verified before analysis]

LIMITATIONS AND RISKS:
- [limitation/risk 1]
- [limitation/risk 2]

EXPERIMENT EXECUTION SPEC:
{
  "runner_type": "universal_tabular_csv, universal_data_file, financial_sentiment_timeseries, event_graph_classification, or NEEDS_NEW_RUNNER",
  "task_type": "classification, regression, auto, or inspect",
  "dataset_url": "primary direct public data file URL, raw GitHub file URL, local data path, or TO_VERIFY",
  "dataset_urls": ["one or more direct public data file URLs or local data paths"],
  "dataset_name": "dataset name",
  "target_column": "exact target column name, AUTO_TARGET, or TO_VERIFY",
  "feature_columns": ["column name or AUTO_NUMERIC"],
  "baseline": "majority_class for classification or mean_prediction for regression",
  "success_metric": "accuracy, mae, rmse, or r2",
  "success_threshold": 0.0,
  "threshold_direction": "greater_or_equal or less_or_equal",
  "notes_for_experiment_agent": "specific instructions for loading and evaluating the dataset"
}

Rules for EXPERIMENT EXECUTION SPEC:
- The JSON must be valid JSON.
- Use runner_type universal_tabular_csv when the experiment can be run from one or more direct/local CSV files with classification, regression, or auto task inference.
- Use runner_type universal_data_file when the experiment can start from direct downloadable CSV, TSV, JSON, JSONL, NDJSON, or ZIP files, even if those files need inspection before modeling.
- Use task_type inspect with universal_data_file when the files can be downloaded/inspected but the target column or modeling task is not yet executable.
- Use runner_type financial_sentiment_timeseries for stock-return forecasting experiments that combine OHLCV data, financial news/headlines, FinBERT or sentiment features, FRED/VIX regime data, and time-series regression targets.
- financial_sentiment_timeseries can run a safe baseline from local/direct OHLCV files or optional yfinance downloads, and it can use headline files when directly provided. It cannot automatically access Kaggle pages without credentials.
- Use runner_type event_graph_classification when the experiment starts from event records that can be loaded from direct JSON, JSONL, CSV, TSV, or ZIP files and transformed into source-target graphs for classification. This includes passing networks, transaction networks, communication networks, citation/event logs, and other relational event data.
- Use runner_type NEEDS_NEW_RUNNER when the real experiment requires new data collection, lab or clinical procedures, human-subject intervention, web scraping, credentialed APIs, API pagination, NLP extraction from many documents, images, PDFs, custom simulation, reinforcement learning, complex time series/backtesting, causal inference, SHAP, bootstrapping, or unsupported metrics.
- Use AUTO_TARGET when a direct CSV is available but its schema has not been inspected yet.
- Use task_type auto when a direct CSV is available but the target type is not known yet.
- Use TO_VERIFY only when no direct executable CSV or local CSV path is available.
- dataset_url and every item in dataset_urls must be direct downloadable file URLs or local/public paths the Experiment Agent can read. A GitHub repository home page is not enough.
- Prefer direct file URLs listed in the public dataset search results. If at least one direct data file URL exists and is relevant to the actual experiment, do not leave dataset_url as TO_VERIFY.
- Do not use an unrelated downloadable file as the official experiment dataset only because it is downloadable.
- If direct files are only smoke tests or are not suitable for the real research question, set runner_type to NEEDS_NEW_RUNNER and explain the needed runner.
"""


SUPPORTED_DIRECT_DATA_SUFFIXES = (".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".zip")
NON_DATA_FILE_MARKERS = (
    ".babelrc",
    ".claude/",
    ".editorconfig",
    ".eslintrc",
    ".github/",
    ".gitignore",
    ".markdownlint",
    ".prettierrc",
    "cargo.lock",
    "composer.lock",
    "config/",
    "eslint.config",
    "flake.lock",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pyproject.toml",
    "requirements.txt",
    "settings.json",
    "tsconfig",
    "yarn.lock",
)
RELEVANCE_STOPWORDS = {
    "about",
    "after",
    "also",
    "analysis",
    "and",
    "any",
    "are",
    "auto",
    "available",
    "based",
    "before",
    "between",
    "candidate",
    "classification",
    "data",
    "dataset",
    "datasets",
    "direct",
    "does",
    "experiment",
    "file",
    "files",
    "from",
    "github",
    "huggingface",
    "into",
    "json",
    "main",
    "model",
    "models",
    "public",
    "research",
    "results",
    "source",
    "study",
    "task",
    "that",
    "the",
    "this",
    "using",
    "with",
}
GENERIC_ANALYSIS_TOKENS = {
    "accuracy",
    "algorithm",
    "algorithms",
    "analysis",
    "analytics",
    "auc",
    "baseline",
    "benchmarks",
    "benchmark",
    "classification",
    "classifier",
    "classifiers",
    "csv",
    "data",
    "dataset",
    "datasets",
    "deep",
    "detect",
    "detection",
    "evaluate",
    "evaluated",
    "evaluation",
    "feature",
    "features",
    "forecast",
    "forecasting",
    "learning",
    "machine",
    "metric",
    "metrics",
    "model",
    "modeling",
    "models",
    "neural",
    "predict",
    "predicting",
    "prediction",
    "predictive",
    "regression",
    "results",
    "supervised",
    "test",
    "testing",
    "train",
    "trained",
    "training",
    "transfer",
    "validation",
}

def read_text_or_path(value: str | Path) -> str:
    if isinstance(value, str) and len(value) > 500:
        return value
    path = Path(value)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return str(value)

def github_search_queries(query: str) -> list[str]:
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
        "extent",
        "across",
        "can",
        "are",
        "well",
        "how",
        "does",
        "into",
        "when",
        "where",
        "which",
        "using",
        "based",
        "between",
        "compared",
        "than",
        "their",
        "have",
        "has",
        "had",
        "been",
        "will",
        "would",
        "could",
        "should",
    }
    words = [
        word
        for word in cleaned.split()
        if len(word) > 2 and word.lower() not in stopwords
    ]
    compact = " ".join(words[:10])
    short_compact = " ".join(words[:6])
    tail_compact = " ".join(words[6:14])
    focused = " ".join(
        word
        for word in words
        if word.lower()
        in {
            "scientific",
            "claims",
            "calibration",
            "confidence",
            "probability",
            "llm",
            "large",
            "language",
            "models",
            "hallucination",
            "fact",
            "verification",
        }
    )
    queries = [
        compact,
        short_compact,
        tail_compact,
        focused,
        f"{short_compact} benchmark",
        f"{short_compact} open data",
        f"{short_compact} public dataset",
    ]
    if focused:
        queries.extend([f"{focused} benchmark", f"{focused} public dataset"])
    return [item for item in dict.fromkeys(q.strip() for q in queries) if item]

def search_public_datasets(query: str, limit: int = 12) -> list[dict]:
    sources = []
    sources.extend(search_github_public_datasets(query, limit=limit))
    sources.extend(search_huggingface_datasets(query, limit=limit))
    #sources.extend(search_uci_datasets(query, limit=limit))
    return sources

def search_github_public_datasets(query: str, limit: int = 12) -> list[dict]:
    collected = []
    seen_urls = set()

    for github_query in github_search_queries(query):
        results = search_github_repositories(github_query, limit=max(limit * 2, 20))
        for result in results:
            result["data_files"] = find_github_data_files(result, limit=25)
            if not result["data_files"]:
                continue
            result["csv_files"] = [
                item for item in result["data_files"] if item.get("path", "").lower().endswith(".csv")
            ]
            url = result.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                collected.append(result)
            if len(collected) >= limit:
                return collected

    return collected

def search_github_repositories(query: str, limit: int = 20) -> list[dict]:
    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            params={
                "q": f"{query} dataset data in:description,readme",
                "sort": "stars",
                "order": "desc",
                "per_page": min(max(limit, 1), 50),
            },
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "AutoResearch-Proposal-Agent",
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"GitHub dataset search failed for query '{query}': {exc}")
        return []

    results = []
    for item in response.json().get("items", []):
        results.append(
            {
                "source": "GitHub",
                "name": item.get("full_name", ""),
                "url": item.get("html_url", ""),
                "default_branch": item.get("default_branch") or "main",
                "description": item.get("description") or "",
                "stars": item.get("stargazers_count"),
                "language": item.get("language") or "N/A",
                "updated_at": item.get("updated_at", ""),
            }
        )
    return results

def score_data_file_path(path: str) -> tuple[int, str]:
    lowered = path.lower()
    score = 0
    if any(part in lowered for part in ("data/", "dataset", "datasets", "events", "matches", "lineups")):
        score -= 10
    if any(part in lowered for part in ("readme", "license", "docs", "example", "sample", "test")):
        score += 5
    if lowered.endswith(".csv"):
        score -= 4
    elif lowered.endswith((".jsonl", ".ndjson")):
        score -= 3
    elif lowered.endswith(".json"):
        score -= 2
    elif lowered.endswith(".zip"):
        score -= 1
    return score, path

def looks_like_data_file_path(path: str) -> bool:
    lowered = path.lower().split("?", 1)[0].rstrip(".,;")
    if not lowered.endswith(SUPPORTED_DIRECT_DATA_SUFFIXES):
        return False
    if any(marker in lowered for marker in NON_DATA_FILE_MARKERS):
        return False
    name = lowered.rsplit("/", 1)[-1]
    if name.startswith("."):
        return False
    return True

def find_github_data_files(repo: dict, limit: int = 10) -> list[dict]:
    repo_name = repo.get("name")
    branch = repo.get("default_branch") or "main"
    if not repo_name or "/" not in repo_name:
        return []

    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo_name}/git/trees/{branch}",
            params={"recursive": "1"},
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "AutoResearch-Proposal-Agent",
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return []

    data_files = []
    for item in response.json().get("tree", []):
        path = item.get("path", "")
        if item.get("type") == "blob" and looks_like_data_file_path(path):
            data_files.append(
                {
                    "path": path,
                    "raw_url": f"https://raw.githubusercontent.com/{repo_name}/{branch}/{path}",
                }
            )
    data_files = sorted(data_files, key=lambda item: score_data_file_path(item.get("path", "")))
    return data_files[:limit]

def search_huggingface_datasets(query: str, limit: int = 12) -> list[dict]:
    collected = []
    for hf_query in github_search_queries(query):
        try:
            response = requests.get(
                "https://huggingface.co/api/datasets",
                params={"search": hf_query, "limit": max(limit * 2, 20)},
                headers={"User-Agent": "AutoResearch-Proposal-Agent"},
                timeout=20,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"Hugging Face dataset search failed for query '{hf_query}': {exc}")
            continue

        for item in response.json():
            dataset_id = item.get("id")
            if not dataset_id:
                continue
            data_files = find_huggingface_data_files(dataset_id, limit=25)
            if not data_files:
                continue
            source = {
                "source": "Hugging Face",
                "name": dataset_id,
                "url": f"https://huggingface.co/datasets/{dataset_id}",
                "description": item.get("description") or "",
                "downloads": item.get("downloads"),
                "likes": item.get("likes"),
                "data_files": data_files,
            }
            source["csv_files"] = [
                item for item in source["data_files"] if item.get("path", "").lower().endswith(".csv")
            ]
            if source["url"] not in {entry.get("url") for entry in collected}:
                collected.append(source)
            if len(collected) >= limit:
                return collected
    return collected

def find_huggingface_data_files(dataset_id: str, limit: int = 10) -> list[dict]:
    try:
        response = requests.get(
            f"https://huggingface.co/api/datasets/{dataset_id}/tree/main",
            params={"recursive": "1"},
            headers={"User-Agent": "AutoResearch-Proposal-Agent"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return []

    data_files = []
    for item in response.json():
        path = item.get("path", "")
        item_type = item.get("type", "")
        if item_type == "file" and looks_like_data_file_path(path):
            data_files.append(
                {
                    "path": path,
                    "raw_url": f"https://huggingface.co/datasets/{dataset_id}/resolve/main/{path}",
                }
            )
    data_files = sorted(data_files, key=lambda item: score_data_file_path(item.get("path", "")))
    return data_files[:limit]

def search_uci_datasets(query: str, limit: int = 5) -> list[dict]:
    collected = []
    for uci_query in github_search_queries(query):
        try:
            response = requests.get(
                "https://archive.ics.uci.edu/api/datasets",
                params={"search": uci_query},
                headers={"User-Agent": "AutoResearch-Proposal-Agent"},
                timeout=20,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"UCI dataset search failed for query '{uci_query}': {exc}")
            continue

        payload = response.json()
        results = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(results, list):
            continue

        for item in results:
            dataset_id = item.get("id") or item.get("ID") or item.get("uci_id")
            name = item.get("name") or item.get("Name") or item.get("title") or "UCI dataset"
            source = {
                "source": "UCI",
                "name": name,
                "url": f"https://archive.ics.uci.edu/dataset/{dataset_id}" if dataset_id else "https://archive.ics.uci.edu/",
                "description": item.get("abstract") or item.get("description") or "",
                "csv_files": [],
            }
            if source["url"] not in {entry.get("url") for entry in collected}:
                collected.append(source)
            if len(collected) >= limit:
                return collected
    return collected

def format_public_sources_for_prompt(sources: list[dict]) -> str:
    readable_sources = [
        source for source in sources if source.get("data_files") or source.get("csv_files")
    ]
    if not readable_sources:
        return (
            "No readable direct public dataset files were found automatically from GitHub, Hugging Face, or UCI. "
            "Any dataset required by the proposal must be marked TO_VERIFY."
        )

    lines = []
    for index, source in enumerate(readable_sources[:15], 1):
        data_files = (source.get("data_files") or source.get("csv_files") or [])[:12]
        status = "DIRECT_DATA_FILE_CANDIDATE"
        data_file_lines = "\n".join(
            f"  - {item.get('raw_url')} (path: {item.get('path')})"
            for item in data_files
        )
        lines.append(
            f"[{index}] {source.get('source')} dataset candidate: {source.get('name')}\n"
            f"URL: {source.get('url')}\n"
            f"Important: URL above is only provenance. The executable dataset inputs are the direct files listed below.\n"
            f"Description: {source.get('description') or 'N/A'}\n"
            f"Stars: {source.get('stars')}\n"
            f"Downloads: {source.get('downloads')}\n"
            f"Language: {source.get('language')}\n"
            f"Updated: {source.get('updated_at')}\n"
            f"Direct data files discovered:\n{data_file_lines}\n"
            f"Status: {status}; verify license, schema, documentation, and reproducibility before use.\n"
        )
    return "\n".join(lines)

def direct_data_urls_from_sources_text(public_data_sources: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)]+", public_data_sources)
    data_urls = []
    for url in urls:
        cleaned = url.rstrip(".,;")
        if looks_like_data_file_path(cleaned):
            data_urls.append(cleaned)
    return list(dict.fromkeys(data_urls))

def direct_csv_urls_from_sources_text(public_data_sources: str) -> list[str]:
    return [url for url in direct_data_urls_from_sources_text(public_data_sources) if url.lower().endswith(".csv")]

def relevance_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if token not in RELEVANCE_STOPWORDS and len(token) > 2
    }

def domain_relevance_tokens(text: str) -> set[str]:
    return {
        token
        for token in relevance_tokens(text)
        if token not in GENERIC_ANALYSIS_TOKENS
    }

def source_blocks(public_data_sources: str) -> list[str]:
    blocks = re.split(r"(?m)^\[\d+\]\s+", public_data_sources)
    return [block.strip() for block in blocks if block.strip()]

def relevant_direct_data_urls_from_sources_text(public_data_sources: str, context_text: str) -> list[str]:
    context_tokens = relevance_tokens(context_text)
    context_domain_tokens = domain_relevance_tokens(context_text)
    relevant_urls = []
    for block in source_blocks(public_data_sources):
        urls = direct_data_urls_from_sources_text(block)
        if not urls:
            continue
        block_tokens = relevance_tokens(block)
        overlap = context_tokens & block_tokens
        domain_overlap = context_domain_tokens & domain_relevance_tokens(block)
        if domain_overlap and len(overlap) >= 2:
            relevant_urls.extend(urls)
    return list(dict.fromkeys(relevant_urls))

def proposal_section_text(text: str, heading: str) -> str:
    upper_text = text.upper()
    start = upper_text.find(heading)
    if start == -1:
        return ""
    start += len(heading)
    next_starts = [
        upper_text.find(next_heading, start)
        for next_heading in REQUIRED_PROPOSAL_SECTIONS
        if next_heading != heading and upper_text.find(next_heading, start) != -1
    ]
    end = min(next_starts) if next_starts else len(text)
    return text[start:end].strip()

def proposal_relevance_context(text: str) -> str:
    sections = [
        proposal_section_text(text, "RESEARCH QUESTION:"),
        proposal_section_text(text, "HYPOTHESIS:"),
        proposal_section_text(text, "EXPERIMENT DESIGN:") or proposal_section_text(text, "DATA ANALYSIS DESIGN:"),
        proposal_section_text(text, "METHODOLOGY:") or proposal_section_text(text, "ANALYSIS METHODOLOGY:"),
        proposal_section_text(text, "KEY VARIABLES:"),
    ]
    context = "\n".join(section for section in sections if section)
    return context or text[:2000]

def read_agent_stream(request_id: str) -> str:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID,
    }
    response = requests.get(
        f"{BASE_URL.rstrip('/')}/api/agent/run/stream",
        headers=headers,
        params={"requestId": request_id},
        stream=True,
        timeout=(30, 300),
    )
    response.encoding = "utf-8"
    response.raise_for_status()

    full_response = ""
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

    if not full_response.strip():
        raise RuntimeError("Proposal agent stream ended without returning text.")
    return full_response.strip()

REQUIRED_PROPOSAL_SECTIONS = [
    "RESEARCH QUESTION:",
    "HYPOTHESIS:",
    "EXPERIMENT DESIGN:",
    "PUBLIC DATA SOURCES:",
    "DATA COLLECTION PLAN:",
    "METHODOLOGY:",
    "KEY VARIABLES:",
    "SUCCESS CRITERIA:",
    "FEASIBILITY CHECK:",
    "LIMITATIONS AND RISKS:",
    "EXPERIMENT EXECUTION SPEC:",
]

def extract_execution_spec(text: str) -> dict | None:
    marker_index = text.upper().find("EXPERIMENT EXECUTION SPEC:")
    if marker_index == -1:
        return None
    json_start = text.find("{", marker_index)
    if json_start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(json_start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[json_start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None

def replace_execution_spec(text: str, spec: dict) -> str:
    marker = "EXPERIMENT EXECUTION SPEC:"
    marker_index = text.upper().find(marker)
    replacement = json.dumps(spec, indent=2)
    if marker_index == -1:
        return text.rstrip() + f"\n\n{marker}\n{replacement}\n"

    json_start = text.find("{", marker_index)
    if json_start == -1:
        return text[: marker_index + len(marker)].rstrip() + f"\n{replacement}\n"

    depth = 0
    in_string = False
    escape = False
    for index in range(json_start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[:json_start] + replacement + text[index + 1 :]
    return text[:json_start] + replacement + "\n"

def text_marks_dataset_as_unsuitable(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "not suitable for the primary",
            "not suitable for the actual",
            "not suitable for the full",
            "only as a preliminary",
            "pipeline validation",
            "smoke test",
        )
    )

def valid_proposal_sections(text: str) -> bool:
    upper_text = text.upper()
    return all(section in upper_text for section in REQUIRED_PROPOSAL_SECTIONS)

def validate_proposal_output(text: str, public_data_sources: str = "") -> tuple[bool, str]:
    if not text.strip():
        return False, "Proposal output was empty."
    if not valid_proposal_sections(text):
        return False, "Proposal output is missing required sections."

    spec = extract_execution_spec(text)
    if not isinstance(spec, dict):
        return False, "Proposal output is missing a valid JSON EXPERIMENT EXECUTION SPEC."

    required_keys = {
        "runner_type",
        "task_type",
        "dataset_url",
        "dataset_urls",
        "dataset_name",
        "target_column",
        "feature_columns",
        "baseline",
        "success_metric",
        "success_threshold",
        "threshold_direction",
        "notes_for_experiment_agent",
    }
    missing_keys = sorted(required_keys - set(spec))
    if missing_keys:
        return False, "EXPERIMENT EXECUTION SPEC is missing keys: " + ", ".join(missing_keys)

    if str(spec.get("runner_type", "")).lower() == "universal_tabular_csv" and text_marks_dataset_as_unsuitable(text):
        return False, "EXPERIMENT EXECUTION SPEC uses an unsuitable smoke-test CSV as the primary dataset."

    direct_data_urls = relevant_direct_data_urls_from_sources_text(
        public_data_sources,
        proposal_relevance_context(text),
    )
    all_direct_data_urls = direct_data_urls_from_sources_text(public_data_sources)
    if direct_data_urls and not text_marks_dataset_as_unsuitable(text):
        urls = spec.get("dataset_urls") if isinstance(spec.get("dataset_urls"), list) else []
        usable_urls = [
            str(value).strip()
            for value in [spec.get("dataset_url"), *urls]
            if str(value).strip() and str(value).strip().upper() != "TO_VERIFY"
        ]
        if not usable_urls:
            return False, "Direct data file candidates exist, but dataset_url is still TO_VERIFY."
        if str(spec.get("task_type", "")).strip().upper() == "TO_VERIFY":
            return False, "Direct data file candidates exist, but task_type is still TO_VERIFY."
        if (
            str(spec.get("target_column", "")).strip().upper() == "TO_VERIFY"
            and str(spec.get("runner_type", "")).lower() not in {"universal_data_file", "event_graph_classification"}
        ):
            return False, "Direct data file candidates exist, but target_column is still TO_VERIFY."
    elif all_direct_data_urls:
        urls = spec.get("dataset_urls") if isinstance(spec.get("dataset_urls"), list) else []
        usable_urls = [
            str(value).strip()
            for value in [spec.get("dataset_url"), *urls]
            if str(value).strip() and str(value).strip().upper() != "TO_VERIFY"
        ]
        unrelated_urls = [url for url in usable_urls if url in all_direct_data_urls]
        if unrelated_urls:
            return False, "EXPERIMENT EXECUTION SPEC uses direct data files that do not appear relevant to the proposal."
    return True, "ok"

def local_data_execution_spec(
    public_data_sources: str,
    existing_spec: dict | None = None,
    context_text: str = "",
) -> dict | None:
    direct_data_urls = relevant_direct_data_urls_from_sources_text(public_data_sources, context_text)
    if not direct_data_urls:
        return None

    spec = dict(existing_spec or {})
    existing_urls = spec.get("dataset_urls") if isinstance(spec.get("dataset_urls"), list) else []
    usable_urls = [
        str(url).strip()
        for url in [spec.get("dataset_url"), *existing_urls]
        if str(url).strip()
        and str(url).strip().upper() != "TO_VERIFY"
        and str(url).strip() in direct_data_urls
    ]
    dataset_urls = usable_urls or direct_data_urls[:5]
    all_csv = all(url.lower().endswith(".csv") for url in dataset_urls)
    has_event_like_json = any(
        url.lower().endswith((".json", ".jsonl", ".ndjson", ".zip"))
        and any(token in url.lower() for token in ("event", "events", "match", "matches", "lineup", "pass", "graph"))
        for url in dataset_urls
    )
    runner_type = "universal_tabular_csv" if all_csv else "universal_data_file"
    if has_event_like_json:
        runner_type = "event_graph_classification"

    spec.update(
        {
            "runner_type": runner_type,
            "task_type": "auto" if runner_type != "universal_data_file" else "inspect",
            "dataset_url": dataset_urls[0],
            "dataset_urls": dataset_urls,
            "target_column": "AUTO_TARGET" if runner_type == "universal_tabular_csv" else "TO_VERIFY",
            "feature_columns": ["AUTO_NUMERIC"] if runner_type != "event_graph_classification" else ["AUTO_GRAPH_FEATURES"],
            "baseline": "majority_class for classification or mean_prediction for regression",
            "success_metric": "accuracy" if runner_type != "universal_data_file" else "inspect",
            "success_threshold": 0.0,
            "threshold_direction": "greater_or_equal",
            "notes_for_experiment_agent": (
                "Direct data file candidates were found by the Proposal stage. "
                "The Experiment Agent should load the files, inspect schema, and use the selected broad runner."
            ),
        }
    )
    if not spec.get("dataset_name") or str(spec.get("dataset_name")).upper() == "TO_VERIFY":
        spec["dataset_name"] = "Direct public data file candidate"
    return spec

def local_csv_execution_spec(public_data_sources: str, existing_spec: dict | None = None) -> dict | None:
    return local_data_execution_spec(public_data_sources, existing_spec)

def locally_repair_execution_spec(text: str, public_data_sources: str) -> str | None:
    if text_marks_dataset_as_unsuitable(text):
        return None
    spec = local_data_execution_spec(
        public_data_sources,
        extract_execution_spec(text),
        proposal_relevance_context(text),
    )
    if spec is None:
        return None
    return replace_execution_spec(text, spec)

def repair_proposal_output(raw_output: str, research_question: str, deep_literature_review: str, public_data_sources: str, reason: str) -> str:
    repair_prompt = f"""
You are repairing the Proposal Agent output for an autonomous research pipeline.

The previous output was invalid because:
{reason}

Rewrite it into the exact required format. Do not include commentary before or after the proposal.
If direct CSV URLs are listed and relevant, use runner_type universal_tabular_csv, task_type auto, target_column AUTO_TARGET, and feature_columns ["AUTO_NUMERIC"].
If direct JSON/JSONL/TSV/ZIP data files are listed and relevant, use runner_type universal_data_file with task_type inspect, unless the experiment is clearly a relational event graph task.
If the experiment is a relational event graph task with direct event files, use runner_type event_graph_classification.
If the available files are only smoke tests or unrelated to the real data analysis, use runner_type NEEDS_NEW_RUNNER and explain the needed runner.
Do not invent datasets, URLs, target columns, metrics, citations, or results.
Do not use numeric citation markers. Convert any cited prior work to author-year format.

{PROPOSAL_SYSTEM_PROMPT}

Selected research question:
{research_question}

Deep literature review:
{deep_literature_review}

Public dataset search results:
{public_data_sources}

Invalid previous output:
{raw_output}
"""
    return call_proposal_api(repair_prompt, label="Proposal repair")

def call_proposal_api(user_input: str, label: str = "Proposal") -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-Principal-Id": PRINCIPAL_ID,
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
            return read_agent_stream(request_id)
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

def run_proposal_agent(
    research_question: str,
    deep_literature_review: str,
    public_data_sources: str = "",
) -> str:
    user_input = (
        PROPOSAL_SYSTEM_PROMPT
        + "\n\nSelected research question:\n"
        + research_question
        + "\n\nDeep literature review:\n"
        + deep_literature_review
        + "\n\nPublic dataset search results from GitHub, Hugging Face, and UCI:\n"
        + public_data_sources
    )
    raw_output = call_proposal_api(user_input, label="Proposal")
    is_valid, reason = validate_proposal_output(raw_output, public_data_sources)
    if is_valid:
        return raw_output

    local_repair = locally_repair_execution_spec(raw_output, public_data_sources)
    if local_repair:
        repaired_is_valid, repaired_reason = validate_proposal_output(local_repair, public_data_sources)
        if repaired_is_valid:
            print(f"Proposal output invalid; fixed execution spec locally. Reason: {reason}")
            return local_repair
        print(f"Local proposal repair was not enough. Reason: {repaired_reason}")

    print(f"Proposal output invalid; attempting format repair. Reason: {reason}")
    try:
        repaired = repair_proposal_output(raw_output, research_question, deep_literature_review, public_data_sources, reason)
        repaired_is_valid, repaired_reason = validate_proposal_output(repaired, public_data_sources)
        if repaired_is_valid:
            return repaired
        local_repair = locally_repair_execution_spec(repaired, public_data_sources)
        if local_repair:
            local_is_valid, local_reason = validate_proposal_output(local_repair, public_data_sources)
            if local_is_valid:
                print(f"Proposal repair output had an invalid execution spec; fixed it locally. Reason: {repaired_reason}")
                return local_repair
            print(f"Local repair after proposal repair was not enough. Reason: {local_reason}")
        print(f"Proposal repair still invalid; using structured fallback. Reason: {repaired_reason}")
        return fallback_proposal(research_question, repaired_reason, public_data_sources)
    except Exception as exc:
        print(f"Proposal repair failed; using structured fallback. Reason: {exc}")
        return fallback_proposal(research_question, f"{reason} Repair failed: {exc}", public_data_sources)

def fallback_proposal(research_question: str, reason: str, public_data_sources: str = "") -> str:
    use_csv_fallback = (
        relevant_direct_data_urls_from_sources_text(public_data_sources, research_question + "\n" + reason)
        and "unsuitable" not in reason.lower()
        and "smoke" not in reason.lower()
    )
    if use_csv_fallback:
        execution_spec = local_data_execution_spec(public_data_sources, context_text=research_question + "\n" + reason) or {}
    else:
        execution_spec = {
            "runner_type": "NEEDS_NEW_RUNNER",
            "task_type": "TO_VERIFY",
            "dataset_url": "TO_VERIFY",
            "dataset_urls": ["TO_VERIFY"],
            "dataset_name": "TO_VERIFY",
            "target_column": "TO_VERIFY",
            "feature_columns": ["TO_VERIFY"],
            "baseline": "TO_VERIFY",
            "success_metric": "TO_VERIFY",
            "success_threshold": 0.0,
            "threshold_direction": "TO_VERIFY",
            "notes_for_experiment_agent": "Proposal generation failed or requires a custom runner before execution.",
        }
    spec_text = json.dumps(execution_spec, indent=2)
    return f"""RESEARCH QUESTION:
{research_question}

HYPOTHESIS:
Proposal generation is pending because the live Proposal Agent was unavailable.

EXPERIMENT DESIGN:
Pending. The analysis must be designed from verified public datasets identified in the Deep Literature stage.

PUBLIC DATA SOURCES:
- TO_VERIFY: Public datasets named in the Deep Literature review must be verified before experiment execution.

DATA COLLECTION PLAN:
The Experiment Agent should retrieve only confirmed public datasets from prior work, Kaggle, Hugging Face Datasets, UCI, Papers With Code, arXiv-linked repositories, GitHub, or other legitimate public repositories.

METHODOLOGY:
Pending. Do not run or report a data analysis until public data sources, baselines, metrics, and evaluation protocol are verified.

KEY VARIABLES:
- Independent variables: TO_VERIFY
- Dependent variables: TO_VERIFY
- Control variables: TO_VERIFY

SUCCESS CRITERIA:
- Data source is public and reproducible.
- Metrics and baselines are explicitly defined.
- Results can be independently reproduced from downloaded/public data.

FEASIBILITY CHECK:
Fallback proposal only. Live proposal generation failed: {reason}

LIMITATIONS AND RISKS:
- The data analysis design is not complete.
- Dataset availability has not been verified.

EXPERIMENT EXECUTION SPEC:
{spec_text}
"""

def run_proposal_stage(research_question: str, deep_literature_review: str | Path) -> str:
    print("\n[Proposal Agent] Orchestrating proposal subagents...")
    deep_literature_text = read_text_or_path(deep_literature_review)

    try:
        try:
            from .proposal.hypothesis_agent import run_hypothesis_agent
            from .proposal.dataset_agent import dataset_report_to_prompt_text, run_dataset_agent
            from .proposal.schema_agent import run_schema_agent
            from .proposal.analysis_agent import run_analysis_agent
            from .proposal.final_agent_prop import run_final_agent_prop
        except ImportError:
            from proposal.hypothesis_agent import run_hypothesis_agent
            from proposal.dataset_agent import dataset_report_to_prompt_text, run_dataset_agent
            from proposal.schema_agent import run_schema_agent
            from proposal.analysis_agent import run_analysis_agent
            from proposal.final_agent_prop import run_final_agent_prop

        proposal_dir = Path("paper_runs/latest/proposal")
        proposal_dir.mkdir(parents=True, exist_ok=True)

        print("[Proposal Agent] Running Hypothesis Agent and Dataset Agent in parallel...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            hypothesis_future = executor.submit(
                run_hypothesis_agent,
                research_question,
                deep_literature_text,
            )
            dataset_future = executor.submit(
                run_dataset_agent,
                research_question,
                proposal_dir / "dataset",
            )

            hypothesis_output = hypothesis_future.result()
            dataset_report = dataset_future.result()

        (proposal_dir / "hypothesis_output.md").write_text(hypothesis_output, encoding="utf-8")

        print("[Proposal Agent] Running Schema Agent...")
        schema_report = run_schema_agent(dataset_report, proposal_dir / "schema")

        print("[Proposal Agent] Running Analysis Agent...")
        analysis_spec = run_analysis_agent(hypothesis_output, dataset_report, schema_report)
        (proposal_dir / "analysis_spec.json").write_text(json.dumps(analysis_spec, indent=2), encoding="utf-8")

        final_proposal = run_final_agent_prop(
            research_question,
            hypothesis_output,
            dataset_report,
            schema_report,
            analysis_spec,
        )
        (proposal_dir / "final_proposal.md").write_text(final_proposal, encoding="utf-8")

        public_sources_text = dataset_report_to_prompt_text(dataset_report)
        is_valid, reason = validate_proposal_output(final_proposal, public_sources_text)
        if is_valid:
            return final_proposal

        repaired = locally_repair_execution_spec(final_proposal, public_sources_text)
        if repaired:
            repaired_is_valid, repaired_reason = validate_proposal_output(repaired, public_sources_text)
            if repaired_is_valid:
                print(f"Final proposal needed local execution-spec repair. Reason: {reason}")
                (proposal_dir / "final_proposal.md").write_text(repaired, encoding="utf-8")
                return repaired
            print(f"Final proposal repair was not enough. Reason: {repaired_reason}")

        print(f"Final proposal invalid; using fallback. Reason: {reason}")
        return fallback_proposal(research_question, reason, public_sources_text)
    except Exception as exc:
        print(f"Proposal failed; using placeholder. Reason: {exc}")
        return fallback_proposal(research_question, str(exc), "")

if __name__ == "__main__":
    question = input("Enter selected research question: ")
    review_path = input("Enter deep literature review path or paste text: ")
    print(run_proposal_stage(question, review_path))
