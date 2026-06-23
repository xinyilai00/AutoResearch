from __future__ import annotations

import json
import re
import time
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
Present an experiment based on existing literature and provide a hypothesis for the research question.

Critical rules:
- The experiment CANNOT be fake.
- The experiment must be possible to implement using only public data, prior-work datasets, or data obtainable from public databases/repositories such as arXiv, Semantic Scholar, OpenAlex, Kaggle, Hugging Face Datasets, UCI, Papers With Code, PubMed, Crossref, GitHub, or other legitimate public sources.
- Do not claim that a dataset exists unless it is named in the deep literature review, listed in the public dataset search results, or clearly marked as TO_VERIFY.
- Do not fabricate citations, dataset sizes, URLs, metrics, baselines, or prior results.
- If you cite or refer to prior work, use author-year format only, such as (Smith, 2023).
- Do NOT use or preserve numeric citation markers such as [1], [22], [2,5], or [3-6].
- If a required dataset is not confirmed in the provided deep literature review, label it as TO_VERIFY and explain how the Experiment stage should verify it.
- If a GitHub, Hugging Face, or UCI result is used, label it with its source status and explain that the Experiment stage must verify license, data files, documentation quality, schema, and reproducibility before execution.
- The proposal must be implementable by a later Experiment Agent using code and downloaded/public data.
- The proposal must include a machine-readable EXPERIMENT EXECUTION SPEC so the Experiment Agent knows exactly what to download/load, what target column to use, what task type to run, and what metric determines success.
- Prefer experiments that can be run with reasonable compute and reproducible data.
- Do not execute the experiment.
- Do not write code.
- Return plain text only.

Output in this exact format:

RESEARCH QUESTION:
[selected research question]

HYPOTHESIS:
[one testable hypothesis]

EXPERIMENT DESIGN:
[specific experiment design based on the literature]

PUBLIC DATA SOURCES:
- [dataset/source 1]: [what it contains, why it is relevant, whether it is CONFIRMED_FROM_LITERATURE or TO_VERIFY]
- [dataset/source 2]: [same]

DATA COLLECTION PLAN:
[how the Experiment Agent should retrieve or construct the dataset from public sources]

METHODOLOGY:
[models, baselines, analysis methods, validation scheme, and statistical tests]

KEY VARIABLES:
- Independent variables: [...]
- Dependent variables: [...]
- Control variables: [...]

SUCCESS CRITERIA:
- [criterion 1]
- [criterion 2]
- [criterion 3]

FEASIBILITY CHECK:
[why this can be implemented with public/prior-work data only, or what must be verified before running]

LIMITATIONS AND RISKS:
- [limitation/risk 1]
- [limitation/risk 2]

EXPERIMENT EXECUTION SPEC:
{
  "runner_type": "universal_tabular_csv or NEEDS_NEW_RUNNER",
  "task_type": "classification, regression, or auto",
  "dataset_url": "primary direct public CSV URL, raw GitHub CSV URL, local CSV path, or TO_VERIFY",
  "dataset_urls": ["one or more direct public CSV URLs, raw GitHub CSV URLs, or local CSV paths"],
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
- Use runner_type NEEDS_NEW_RUNNER when the real experiment requires web scraping, credentialed APIs, images, PDFs, custom simulation, reinforcement learning, complex time series/backtesting, causal inference, SHAP, bootstrapping, or unsupported metrics.
- Use AUTO_TARGET when a direct CSV is available but its schema has not been inspected yet.
- Use task_type auto when a direct CSV is available but the target type is not known yet.
- Use TO_VERIFY only when no direct executable CSV or local CSV path is available.
- dataset_url and every item in dataset_urls must be direct downloadable CSV URLs or local/public paths the Experiment Agent can read. A GitHub repository home page is not enough.
- Prefer direct CSV URLs listed in the public dataset search results. If at least one direct CSV URL exists and is relevant to the actual experiment, do not leave dataset_url as TO_VERIFY.
- Do not use an unrelated CSV as the official experiment dataset only because it is downloadable.
- If direct CSVs are only smoke tests or are not suitable for the real research question, set runner_type to NEEDS_NEW_RUNNER and explain the needed runner.
"""


def read_text_or_path(value: str | Path) -> str:
    path = Path(value)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return str(value)


def github_search_queries(query: str) -> list[str]:
    cleaned = re.sub(r"[^A-Za-z0-9\s-]", " ", query)
    words = [
        word
        for word in cleaned.split()
        if len(word) > 2
        and word.lower()
        not in {
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
        }
    ]
    compact = " ".join(words[:10])
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
    queries = [focused, compact, "scientific claims calibration dataset", "llm hallucination dataset"]
    return [item for item in dict.fromkeys(q.strip() for q in queries) if item]


def search_public_datasets(query: str, limit: int = 5) -> list[dict]:
    sources = []
    sources.extend(search_github_public_datasets(query, limit=limit))
    sources.extend(search_huggingface_datasets(query, limit=limit))
    #sources.extend(search_uci_datasets(query, limit=limit))
    return sources


def search_github_public_datasets(query: str, limit: int = 5) -> list[dict]:
    collected = []
    seen_urls = set()

    for github_query in github_search_queries(query):
        results = search_github_repositories(github_query, limit=limit)
        for result in results:
            result["csv_files"] = find_github_csv_files(result, limit=3)
            url = result.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                collected.append(result)
            if len(collected) >= limit:
                return collected

    return collected


def search_github_repositories(query: str, limit: int = 5) -> list[dict]:
    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            params={
                "q": f"{query} dataset data in:description,readme",
                "sort": "stars",
                "order": "desc",
                "per_page": limit,
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


def find_github_csv_files(repo: dict, limit: int = 3) -> list[dict]:
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

    csv_files = []
    for item in response.json().get("tree", []):
        path = item.get("path", "")
        if item.get("type") == "blob" and path.lower().endswith(".csv"):
            csv_files.append(
                {
                    "path": path,
                    "raw_url": f"https://raw.githubusercontent.com/{repo_name}/{branch}/{path}",
                }
            )
            if len(csv_files) >= limit:
                break
    return csv_files


def search_huggingface_datasets(query: str, limit: int = 5) -> list[dict]:
    collected = []
    for hf_query in github_search_queries(query):
        try:
            response = requests.get(
                "https://huggingface.co/api/datasets",
                params={"search": hf_query, "limit": limit},
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
            source = {
                "source": "Hugging Face",
                "name": dataset_id,
                "url": f"https://huggingface.co/datasets/{dataset_id}",
                "description": item.get("description") or "",
                "downloads": item.get("downloads"),
                "likes": item.get("likes"),
                "csv_files": find_huggingface_csv_files(dataset_id, limit=3),
            }
            if source["url"] not in {entry.get("url") for entry in collected}:
                collected.append(source)
            if len(collected) >= limit:
                return collected
    return collected


def find_huggingface_csv_files(dataset_id: str, limit: int = 3) -> list[dict]:
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

    csv_files = []
    for item in response.json():
        path = item.get("path", "")
        item_type = item.get("type", "")
        if item_type == "file" and path.lower().endswith(".csv"):
            csv_files.append(
                {
                    "path": path,
                    "raw_url": f"https://huggingface.co/datasets/{dataset_id}/resolve/main/{path}",
                }
            )
            if len(csv_files) >= limit:
                break
    return csv_files


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
    if not sources:
        return (
            "No public dataset candidates were found automatically from GitHub, Hugging Face, or UCI. "
            "Any dataset required by the proposal must be marked TO_VERIFY."
        )

    lines = []
    for index, source in enumerate(sources, 1):
        csv_files = source.get("csv_files") or []
        status = f"{source.get('source', 'Public source').upper().replace(' ', '_')}_CANDIDATE"
        if csv_files:
            status = "DIRECT_CSV_CANDIDATE"
        csv_lines = "\n".join(
            f"  - {item.get('raw_url')} (path: {item.get('path')})"
            for item in csv_files
        ) or "  - None found automatically; dataset_url must remain TO_VERIFY unless manually verified."
        lines.append(
            f"[{index}] {source.get('source')} dataset candidate: {source.get('name')}\n"
            f"URL: {source.get('url')}\n"
            f"Description: {source.get('description') or 'N/A'}\n"
            f"Stars: {source.get('stars')}\n"
            f"Downloads: {source.get('downloads')}\n"
            f"Language: {source.get('language')}\n"
            f"Updated: {source.get('updated_at')}\n"
            f"Direct CSV files discovered:\n{csv_lines}\n"
            f"Status: {status}; verify license, schema, documentation, and reproducibility before use.\n"
        )
    return "\n".join(lines)


def direct_csv_urls_from_sources_text(public_data_sources: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)]+", public_data_sources)
    csv_urls = []
    for url in urls:
        cleaned = url.rstrip(".,;")
        if (
            cleaned.lower().endswith(".csv")
            or "raw.githubusercontent.com" in cleaned
            or ("huggingface.co/datasets/" in cleaned and "/resolve/" in cleaned)
        ):
            csv_urls.append(cleaned)
    return list(dict.fromkeys(csv_urls))


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

    direct_csv_urls = direct_csv_urls_from_sources_text(public_data_sources)
    if direct_csv_urls and not text_marks_dataset_as_unsuitable(text):
        urls = spec.get("dataset_urls") if isinstance(spec.get("dataset_urls"), list) else []
        usable_urls = [
            str(value).strip()
            for value in [spec.get("dataset_url"), *urls]
            if str(value).strip() and str(value).strip().upper() != "TO_VERIFY"
        ]
        if not usable_urls:
            return False, "Direct CSV candidates exist, but dataset_url is still TO_VERIFY."
        if str(spec.get("task_type", "")).strip().upper() == "TO_VERIFY":
            return False, "Direct CSV candidates exist, but task_type is still TO_VERIFY."
        if str(spec.get("target_column", "")).strip().upper() == "TO_VERIFY":
            return False, "Direct CSV candidates exist, but target_column is still TO_VERIFY."
    return True, "ok"


def local_csv_execution_spec(public_data_sources: str, existing_spec: dict | None = None) -> dict | None:
    direct_csv_urls = direct_csv_urls_from_sources_text(public_data_sources)
    if not direct_csv_urls:
        return None

    spec = dict(existing_spec or {})
    existing_urls = spec.get("dataset_urls") if isinstance(spec.get("dataset_urls"), list) else []
    usable_urls = [
        str(url).strip()
        for url in [spec.get("dataset_url"), *existing_urls]
        if str(url).strip()
        and str(url).strip().upper() != "TO_VERIFY"
        and str(url).strip() in direct_csv_urls
    ]
    dataset_urls = usable_urls or direct_csv_urls[:3]

    spec.update(
        {
            "runner_type": "universal_tabular_csv",
            "task_type": "auto",
            "dataset_url": dataset_urls[0],
            "dataset_urls": dataset_urls,
            "target_column": "AUTO_TARGET",
            "feature_columns": ["AUTO_NUMERIC"],
            "baseline": "majority_class for classification or mean_prediction for regression",
            "success_metric": "accuracy",
            "success_threshold": 0.0,
            "threshold_direction": "greater_or_equal",
            "notes_for_experiment_agent": (
                "Direct CSV candidates were found by the Proposal stage. "
                "The Experiment Agent should load the CSV, infer target_column and task_type, "
                "then run the universal tabular baseline."
            ),
        }
    )
    if not spec.get("dataset_name") or str(spec.get("dataset_name")).upper() == "TO_VERIFY":
        spec["dataset_name"] = "Direct public CSV candidate"
    return spec


def locally_repair_execution_spec(text: str, public_data_sources: str) -> str | None:
    if text_marks_dataset_as_unsuitable(text):
        return None
    spec = local_csv_execution_spec(public_data_sources, extract_execution_spec(text))
    if spec is None:
        return None
    return replace_execution_spec(text, spec)


def repair_proposal_output(raw_output: str, research_question: str, deep_literature_review: str, public_data_sources: str, reason: str) -> str:
    repair_prompt = f"""
You are repairing the Proposal Agent output for an autonomous research pipeline.

The previous output was invalid because:
{reason}

Rewrite it into the exact required format. Do not include commentary before or after the proposal.
If direct CSV URLs are listed and they are relevant to the actual experiment, use runner_type universal_tabular_csv, task_type auto, target_column AUTO_TARGET, and feature_columns ["AUTO_NUMERIC"].
If the available CSVs are only smoke tests or unrelated to the real experiment, use runner_type NEEDS_NEW_RUNNER and explain the needed runner.
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
        print(f"Proposal repair still invalid; using structured fallback. Reason: {repaired_reason}")
        return fallback_proposal(research_question, repaired_reason, public_data_sources)
    except Exception as exc:
        print(f"Proposal repair failed; using structured fallback. Reason: {exc}")
        return fallback_proposal(research_question, f"{reason} Repair failed: {exc}", public_data_sources)


def fallback_proposal(research_question: str, reason: str, public_data_sources: str = "") -> str:
    use_csv_fallback = (
        direct_csv_urls_from_sources_text(public_data_sources)
        and "unsuitable" not in reason.lower()
        and "smoke" not in reason.lower()
    )
    if use_csv_fallback:
        execution_spec = local_csv_execution_spec(public_data_sources) or {}
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
Pending. The experiment must be designed from verified public datasets identified in the Deep Literature stage.

PUBLIC DATA SOURCES:
- TO_VERIFY: Public datasets named in the Deep Literature review must be verified before experiment execution.

DATA COLLECTION PLAN:
The Experiment Agent should retrieve only confirmed public datasets from prior work, Kaggle, Hugging Face Datasets, UCI, Papers With Code, arXiv-linked repositories, GitHub, or other legitimate public repositories.

METHODOLOGY:
Pending. Do not run or report an experiment until public data sources, baselines, metrics, and evaluation protocol are verified.

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
- The experiment design is not complete.
- Dataset availability has not been verified.

EXPERIMENT EXECUTION SPEC:
{spec_text}
"""


def run_proposal_stage(research_question: str, deep_literature_review: str | Path) -> str:
    print("\n[Proposal Agent] Designing experiment proposal...")
    deep_literature_text = read_text_or_path(deep_literature_review)
    print("[Proposal Agent] Searching public dataset candidates...")
    public_sources = search_public_datasets(research_question)
    public_sources_text = format_public_sources_for_prompt(public_sources)
    try:
        return run_proposal_agent(research_question, deep_literature_text, public_sources_text)
    except Exception as exc:
        print(f"Proposal failed; using placeholder. Reason: {exc}")
        return fallback_proposal(research_question, str(exc), public_sources_text)


if __name__ == "__main__":
    question = input("Enter selected research question: ")
    review_path = input("Enter deep literature review path or paste text: ")
    print(run_proposal_stage(question, review_path))
