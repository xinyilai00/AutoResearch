from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


RUN_DIR = Path("paper_runs/latest")
BENCHMARK_DIR = RUN_DIR / "benchmarks"
SUPPORTED_DATA_SUFFIXES = (".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".zip", ".parquet")
BENCHMARK_NAME_HINTS = ("app", "benchmark", "eval", "evaluate", "experiment", "main", "model", "predict", "prediction", "train", "test", "run")
BENCHMARK_CODE_HINTS = (
    "accuracy_score",
    "association",
    "gwas",
    "genome-wide",
    "genome wide",
    "gradientboost",
    "logisticregression",
    "p-value",
    "p.value",
    "plink",
    "randomforest",
    "sklearn",
    "snp",
    "train_test_split",
    "xgboost",
    ".fit(",
    ".predict(",
)
METRIC_HINTS = ("accuracy", "f1", "auc", "roc", "mae", "rmse", "r2", "precision", "recall", "loss")
DEFAULT_GIT_CLONE_TIMEOUT_SECONDS = 25
DEFAULT_MAX_CLONE_ATTEMPTS = 8
MAX_REPO_SIZE_KB = 750_000
REJECT_REPO_TERMS = (
    "actions-openwrt",
    "buildroot",
    "firmware",
    "lede",
    "openwrt",
    "router",
    "uboot",
)
REJECT_REPO_NAMES = (
    ".config",
    "config",
)
DATA_SOURCE_HINTS = (
    "dataset",
    "data",
    "download",
    "wget",
    "curl",
    "kaggle",
    "huggingface",
    "zenodo",
    "figshare",
    "osf",
    "clinvar",
    "uniprot",
    "ncbi",
    "s3",
    "ftp",
)
SEARCH_STOP_WORDS = {
    "about",
    "across",
    "analysis",
    "based",
    "between",
    "can",
    "could",
    "data",
    "dataset",
    "datasets",
    "db",
    "does",
    "extent",
    "identified",
    "from",
    "fine",
    "fine-tuned",
    "have",
    "and",
    "into",
    "more",
    "over",
    "public",
    "publicly",
    "question",
    "reveal",
    "research",
    "study",
    "than",
    "that",
    "their",
    "this",
    "through",
    "tuned",
    "using",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "known",
    "meaningful",
    "rules",
    "varying",
    "degrees",
    "only",
    "specific",
    "single",
    "wide",
    "available",
    "achieve",
    "higher",
    "outperform",
    "compared",
    "classification",
        "classifying",
    "associated",
    "such",
    "predicted",
    "changes",
    "pretrained",
    "representations",
    "consequence",
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


def compact_text(text: str, limit: int = 2000) -> str:
    cleaned = " ".join(str(text).split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def research_keywords(research_question: str, limit: int = 10) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_+-]{3,}", research_question.lower())
    keywords = []
    seen = set()
    for word in words:
        if word in SEARCH_STOP_WORDS or word in seen:
            continue
        seen.add(word)
        keywords.append(word)
    return keywords[:limit]


def important_terms(research_question: str) -> list[str]:
    raw_terms = re.findall(r"[A-Za-z][A-Za-z0-9.+-]*", research_question)
    acronyms = []
    for term in raw_terms:
        normalized = term.strip(".,()").lower()
        if normalized.endswith("-based"):
            normalized = normalized.removesuffix("-based")
        normalized_parts = [part for part in re.split(r"[-/]", normalized) if part and part not in SEARCH_STOP_WORDS]
        if len(normalized) >= 2 and (
            term.isupper()
            or any(char.isdigit() for char in term)
            or "-" in term
        ):
            acronyms.extend(normalized_parts)
    keywords = research_keywords(research_question, 24)
    return list(dict.fromkeys([*acronyms, *keywords]))


def keyword_bundles(keywords: list[str], size: int = 3, limit: int = 8) -> list[str]:
    bundles = []
    if not keywords:
        return bundles
    for start in range(0, len(keywords), 2):
        chunk = keywords[start : start + size]
        if len(chunk) >= 2:
            bundles.append(" ".join(chunk))
    for start in range(1, len(keywords), 2):
        chunk = keywords[start : start + size]
        if len(chunk) >= 2:
            bundles.append(" ".join(chunk))
    return list(dict.fromkeys(bundles))[:limit]


def search_query(research_question: str) -> str:
    terms = research_keywords(research_question, 8)
    return " ".join(terms + ["benchmark", "experiment", "dataset"])


def search_queries(research_question: str) -> list[str]:
    keywords = important_terms(research_question)[:12]
    if not keywords:
        return ["machine learning benchmark"]

    queries = []

    # Core topic queries
    core = " ".join(keywords[:3])
    queries.extend([
        f"{core} benchmark",
        f"{core} experiment",
        f"{core} dataset",
        f"{core} github",
    ])

    # Two-keyword combos
    for i in range(min(4, len(keywords) - 1)):
        pair = f"{keywords[i]} {keywords[i + 1]}"
        queries.extend([
            f"{pair} benchmark",
            f"{pair} experiment code",
        ])

    # Single most important keyword + benchmark terms
    queries.extend([
        f"{keywords[0]} benchmark dataset",
        f"{keywords[0]} replication code",
        f"{keywords[0]} experiment github",
    ])

    # Three-keyword combos for variety
    if len(keywords) >= 3:
        queries.extend([
            f"{keywords[0]} {keywords[1]} {keywords[2]}",
            f"{keywords[0]} {keywords[2]} benchmark",
        ])

    print(f"[Proposal Agent] Generated queries: {list(dict.fromkeys(q for q in queries if q.strip()))[:12]}")
    return list(dict.fromkeys(q for q in queries if q.strip()))[:12]


def github_api_json(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AutoResearch-Benchmark-Proposal",
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    request = urllib.request.Request(
        url,
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def generate_search_queries_via_ai(research_question: str) -> list[str]:
    prompt = f"""You are helping find relevant GitHub repositories for a research paper.

Research question: {research_question}

Generate exactly 8 specific GitHub search queries to find self-contained benchmark repositories relevant to this research question.

Rules:
- Each query must be 2-3 words maximum — shorter is better for GitHub search
- Focus on the core technical method or task names only
- Target repos with bundled datasets, no external API keys required
- Queries should be diverse
- Output ONLY the queries, one per line, no numbering, no explanation

Example format:
bert distillation benchmark
transformer pruning pytorch
nlp compression glue
attention efficiency dataset"""

    try:
        from .agent_api import call_agent_api
        from .config import PRINCIPAL_ID
    except ImportError:
        from agent_api import call_agent_api
        from config import PRINCIPAL_ID

    try:
        result = call_agent_api(prompt, "Query Generator", PRINCIPAL_ID)
        queries = [line.strip() for line in result.strip().splitlines() if line.strip()]
        queries = [q for q in queries if 2 <= len(q.split()) <= 6]
        print(f"[Proposal Agent] AI-generated queries: {queries}")
        return queries[:8] if queries else search_queries(research_question)
    except Exception as exc:
        print(f"[Proposal Agent] AI query generation failed, falling back to keyword queries. Reason: {exc}")
        return search_queries(research_question)

def search_github_repos(research_question: str, limit: int = 5) -> list[dict]:
    repos = []
    seen = set()
    failure_count = 0
    first_failure = ""
    for raw_query in generate_search_queries_via_ai(research_question):        
        query = urllib.parse.quote(raw_query)
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
        try:
            payload = github_api_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code in {403, 429}:
                print(f"GitHub benchmark search hit rate limit at '{raw_query}'; stopping GitHub search for this run.")
                break
            failure_count += 1
            first_failure = first_failure or str(exc)
            continue
        except Exception as exc:
            failure_count += 1
            first_failure = first_failure or str(exc)
            continue
        for item in payload.get("items", []):
            name = item.get("full_name", "")
            if not name or name in seen:
                continue
            seen.add(name)
            repos.append(
                {
                    "name": name,
                    "url": item.get("html_url", ""),
                    "clone_url": item.get("clone_url", ""),
                    "description": item.get("description") or "",
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language") or "",
                    "updated_at": item.get("updated_at") or "",
                    "size_kb": item.get("size") or 0,
                    "search_query": raw_query,
                }
            )
    if failure_count and not repos:
        print(f"GitHub benchmark search failed for {failure_count} queries. First error: {first_failure}")
    print(f"[Proposal Agent] Total repos found before scoring: {len(repos)}")
    for r in repos[:5]:
        print(f"  - {r['name']} (stars: {r['stars']}, score: {repo_score(r, research_question)})")
    
    return sorted(repos, key=lambda repo: repo_score(repo, research_question), reverse=True)[: max(limit, 10)]


def huggingface_search_queries(research_question: str) -> list[str]:
    keywords = important_terms(research_question)[:18]
    term_set = set(keywords)
    queries = []
    dataset_terms = [
        term for term in (
            "clinvar",
            "uniprot",
            "cadd",
            "missense",
            "variant",
            "variants",
            "pathogenicity",
            "protein",
            "mutation",
            "stability",
        )
        if term in term_set
    ]
    if "variant" in term_set or "variants" in term_set:
        queries.extend(
            [
                "clinvar variant pathogenicity",
                "missense variant pathogenicity",
                "protein variant classification",
                "variant effect prediction",
            ]
        )
    if "protein" in term_set:
        queries.extend(
            [
                "protein mutation dataset",
                "protein stability dataset",
                "uniprot variant",
            ]
        )
    for bundle in keyword_bundles(dataset_terms or keywords, size=3, limit=5):
        queries.append(bundle)
    return list(dict.fromkeys(query for query in queries if query.strip()))[:10]


def search_huggingface_datasets(research_question: str, limit: int = 5) -> list[dict]:
    datasets = []
    seen = set()
    failure_count = 0
    first_failure = ""
    for raw_query in huggingface_search_queries(research_question):
        query = urllib.parse.quote(raw_query)
        url = f"https://huggingface.co/api/datasets?search={query}&limit={limit}"
        request = urllib.request.Request(url, headers={"User-Agent": "AutoResearch-Benchmark-Proposal"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            failure_count += 1
            first_failure = first_failure or str(exc)
            continue
        for item in payload if isinstance(payload, list) else []:
            dataset_id = item.get("id") or item.get("name", "")
            if not dataset_id or dataset_id in seen:
                continue
            seen.add(dataset_id)
            datasets.append(
                {
                    "id": dataset_id,
                    "downloads": item.get("downloads", 0),
                    "likes": item.get("likes", 0),
                    "tags": item.get("tags", [])[:10],
                    "url": f"https://huggingface.co/datasets/{dataset_id}",
                    "search_query": raw_query,
                }
            )
    if failure_count and not datasets:
        print(f"Hugging Face dataset search failed for {failure_count} queries. First error: {first_failure}")
    return sorted(datasets, key=lambda item: (item.get("downloads", 0), item.get("likes", 0)), reverse=True)[:limit]


def repo_score(repo: dict, research_question: str) -> int:
    haystack = " ".join(
        [
            str(repo.get("name", "")),
            str(repo.get("description", "")),
            str(repo.get("language", "")),
        ]
    ).lower()
    repo_name = str(repo.get("name", "")).lower()
    if any(term in haystack for term in REJECT_REPO_TERMS):
        return -10_000
    if any(repo_name.endswith(f"/{name}") or repo_name == name for name in REJECT_REPO_NAMES):
        return -10_000
    question_tokens = set(research_keywords(research_question, 20))
    score = min(int(repo.get("stars", 0)), 500)
    score += sum(20 for token in question_tokens if token in haystack)
    score += sum(35 for token in ("benchmark", "experiment", "replication", "reproducibility", "dataset", "code") if token in haystack)
    if question_tokens:
        overlap = sum(1 for token in question_tokens if token in haystack)
        score += overlap * overlap * 5
    return score


def choose_repo(repos: list[dict]) -> dict:
    if not repos:
        return {}
    return repos[0]


def safe_repo_dir(repo: dict) -> Path:
    name = str(repo.get("name", "repo")).replace("/", "__")
    return BENCHMARK_DIR / "repos" / name


def clone_repo(repo: dict) -> Path | None:
    clone_url = repo.get("clone_url")
    if not clone_url:
        return None
    repo_size = int(repo.get("size_kb") or 0)
    if repo_size > MAX_REPO_SIZE_KB:
        print(f"Skipping large repo {clone_url}: {repo_size} KB exceeds {MAX_REPO_SIZE_KB} KB.")
        return None
    destination = safe_repo_dir(repo)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (destination / ".git").exists():
        return destination
    if destination.exists():
        shutil.rmtree(destination)
    timeout = int(os.getenv("GIT_CLONE_TIMEOUT_SECONDS", str(DEFAULT_GIT_CLONE_TIMEOUT_SECONDS)))
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", "--filter=blob:none", clone_url, str(destination)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        return destination
    except Exception as exc:
        print(f"Git clone failed for {clone_url}; skipping this candidate. Reason: {exc}")
        return None


def read_small_file(path: Path, limit: int = 6000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def inspect_repo(repo_path: Path | None) -> dict:
    if not repo_path or not repo_path.exists():
        return {"available": False, "reason": "Repository was not cloned."}

    files = [path for path in repo_path.rglob("*") if path.is_file() and ".git" not in path.parts]
    rel_files = [str(path.relative_to(repo_path)) for path in files]
    readmes = [path for path in files if path.name.lower().startswith("readme")]
    requirements = [
        path for path in files
        if path.name.lower() in {"requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml", "setup.py"}
    ]
    script_files = [path for path in files if path.suffix.lower() in {".py", ".ipynb", ".sh", ".r"}]
    benchmark_files = []
    for path in script_files:
        name_match = any(hint in path.name.lower() for hint in BENCHMARK_NAME_HINTS)
        code = read_small_file(path, 12000).lower() if path.suffix.lower() in {".py", ".ipynb", ".r"} else ""
        code_match = any(hint in code for hint in BENCHMARK_CODE_HINTS)
        if name_match or code_match:
            benchmark_files.append(path)
    benchmark_files = benchmark_files[:12]
    data_files = [
        path for path in files
        if path.suffix.lower() in SUPPORTED_DATA_SUFFIXES
    ][:20]

    text_blob = "\n".join(read_small_file(path) for path in [*readmes[:3], *requirements[:3], *benchmark_files[:8]])
    urls = sorted({url.rstrip(".,") for url in re.findall(r"https?://[^\s)\"']+", text_blob)})
    dataset_urls = [
        url for url in urls
        if url.lower().split("?", 1)[0].endswith(SUPPORTED_DATA_SUFFIXES)
    ]
    data_source_urls = [
        url for url in urls
        if any(hint in url.lower() for hint in DATA_SOURCE_HINTS)
    ]
    data_instruction_lines = []
    for line in text_blob.splitlines():
        cleaned = " ".join(line.split())
        lowered = cleaned.lower()
        if cleaned and any(hint in lowered for hint in DATA_SOURCE_HINTS):
            data_instruction_lines.append(cleaned[:240])
            for url in re.findall(r"https?://[^\s)\"'<>]+", cleaned):
                data_source_urls.append(url.rstrip(".,"))
    data_source_urls = list(dict.fromkeys(data_source_urls))
    metrics = sorted({metric for metric in METRIC_HINTS if metric in text_blob.lower()})
    confidence = "low"
    if benchmark_files and (data_files or dataset_urls):
        confidence = "high"
    elif benchmark_files and (data_source_urls or data_instruction_lines):
        confidence = "medium"
    elif data_files or dataset_urls:
        confidence = "medium"

    return {
        "available": True,
        "file_count": len(files),
        "selection_confidence": confidence,
        "readme_files": [str(path.relative_to(repo_path)) for path in readmes[:5]],
        "requirements_files": [str(path.relative_to(repo_path)) for path in requirements[:8]],
        "benchmark_files": [str(path.relative_to(repo_path)) for path in benchmark_files],
        "repo_data_files": [str(path.relative_to(repo_path)) for path in data_files],
        "dataset_urls": dataset_urls[:10],
        "data_source_urls": data_source_urls[:10],
        "data_instruction_lines": list(dict.fromkeys(data_instruction_lines))[:12],
        "metrics": metrics[:8],
        "sample_files": rel_files[:80],
        "text_sample": compact_text(text_blob, 3000),
    }


def download_dataset_urls(urls: list[str], output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for index, url in enumerate(urls[:5], 1):
        name = Path(urllib.parse.urlparse(url).path).name or f"dataset_{index:02d}.dat"
        destination = output_dir / f"dataset_{index:02d}_{name}"
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                destination.write_bytes(response.read())
            downloaded.append(str(destination))
        except Exception as exc:
            print(f"Dataset download failed for {url}: {exc}")
    return downloaded


def choose_dataset_source(repo_inspection: dict, hf_datasets: list[dict]) -> dict:
    repo_dataset_urls = repo_inspection.get("dataset_urls", [])
    repo_data_files = repo_inspection.get("repo_data_files", [])
    data_source_urls = repo_inspection.get("data_source_urls", [])
    data_instruction_lines = repo_inspection.get("data_instruction_lines", [])
    benchmark_files = repo_inspection.get("benchmark_files", [])
    best_hf = sorted(hf_datasets, key=lambda item: (item.get("downloads", 0), item.get("likes", 0)), reverse=True)[0] if hf_datasets else None
    if repo_data_files:
        return {"kind": "repo_bundled_files", "source": repo_data_files, "confidence": "high"}
    if repo_dataset_urls:
        return {"kind": "repo_direct_downloads", "source": repo_dataset_urls, "confidence": "high"}
    if benchmark_files and best_hf:
        return {
            "kind": "repo_benchmark_plus_huggingface",
            "source": {"benchmark_files": benchmark_files, "huggingface": best_hf},
            "confidence": "high",
        }
    if data_source_urls:
        if best_hf:
            return {
                "kind": "repo_data_source_plus_huggingface",
                "source": {"repo_data_source_urls": data_source_urls, "huggingface": best_hf},
                "confidence": "high",
            }
        return {"kind": "repo_data_source_urls", "source": data_source_urls, "confidence": "medium"}
    if data_instruction_lines:
        if best_hf:
            return {
                "kind": "repo_data_instructions_plus_huggingface",
                "source": {"repo_data_instructions": data_instruction_lines, "huggingface": best_hf},
                "confidence": "high",
            }
        return {"kind": "repo_data_instructions", "source": data_instruction_lines, "confidence": "medium"}
    if best_hf:
        return {"kind": "huggingface", "source": best_hf, "confidence": "medium"}
    return {"kind": "repo_internal_or_manual", "source": repo_inspection.get("repo_data_files", []), "confidence": "low"}


def make_hypothesis(research_question: str, repo: dict, repo_inspection: dict, dataset_choice: dict) -> str:
    metric = (repo_inspection.get("metrics") or ["primary benchmark metric"])[0]
    return (
        "Using the benchmark repository's existing dataset, variables, and evaluation protocol, "
        f"a modified replication that adds one transparent comparison factor relevant to '{research_question}' "
        f"will improve or clarify the original benchmark result on {metric} without changing the dataset source."
    )


def repo_is_useful(repo_inspection: dict) -> bool:
    if not repo_inspection.get("available"):
        return False
    return bool(repo_inspection.get("benchmark_files"))


def inspected_repo_score(repo: dict, repo_inspection: dict, research_question: str) -> int:
    if not repo_inspection.get("available"):
        return -1
    if repo_score(repo, research_question) <= -10_000:
        return -1
    if not repo_inspection.get("benchmark_files"):
        return -1
    relevant_terms = [
        term for term in important_terms(research_question)
        if term not in {"model", "models", "deep", "learning", "foundation", "features", "feature"}
    ]
    inspection_text = " ".join(
        [
            str(repo.get("name", "")),
            str(repo.get("description", "")),
            str(repo_inspection.get("text_sample", "")),
            " ".join(repo_inspection.get("sample_files", [])),
        ]
    ).lower()
    if any(term in inspection_text for term in REJECT_REPO_TERMS):
        return -1
    overlap = sum(1 for term in relevant_terms if term in inspection_text)
    if relevant_terms and overlap == 0:
        return -1
    if any(term in set(relevant_terms) for term in {"cat", "cats", "feline"}):
        has_cat_evidence = bool(re.search(r"\b(cat|cats|feline|felis)\b", inspection_text))
        repo_summary_text = " ".join([str(repo.get("name", "")), str(repo.get("description", ""))]).lower()
        has_conflicting_species = bool(
            re.search(r"\b(avian|chicken|poultry|canine|dog|dogs|bovine|cow|cows|equine|horse|horses)\b", repo_summary_text)
        )
        if has_conflicting_species and not has_cat_evidence:
            return -1
    protein_prompt = any(
        term in set(relevant_terms)
        for term in {"alphafold", "protein", "variant", "missense", "pathogenicity", "stability", "uniprot", "clinvar"}
    )
    protein_evidence = sum(
        1
        for term in ("alphafold", "protein", "variant", "missense", "pathogenic", "pathogenicity", "stability", "uniprot", "clinvar")
        if term in inspection_text
    )
    if protein_prompt and protein_evidence == 0:
        return -1
    score = repo_score(repo, research_question)
    score += overlap * overlap * 120
    score += len(repo_inspection.get("dataset_urls", [])) * 120
    score += len(repo_inspection.get("repo_data_files", [])) * 90
    score += len(repo_inspection.get("data_source_urls", [])) * 75
    score += len(repo_inspection.get("data_instruction_lines", [])) * 55
    score += len(repo_inspection.get("benchmark_files", [])) * 70
    score += len(repo_inspection.get("requirements_files", [])) * 35
    score += len(repo_inspection.get("metrics", [])) * 20
    score += len(repo_inspection.get("readme_files", [])) * 10
    if repo_inspection.get("benchmark_files") and (
        repo_inspection.get("repo_data_files") or repo_inspection.get("dataset_urls")
    ):
        score += 250
    if repo_inspection.get("benchmark_files") and (
        repo_inspection.get("data_source_urls") or repo_inspection.get("data_instruction_lines")
    ):
        score += 150
    if repo_inspection.get("selection_confidence") == "high":
        score += 300
    elif repo_inspection.get("selection_confidence") == "medium":
        score += 150
    return score


def select_and_clone_repo(repos: list[dict], research_question: str) -> tuple[dict, Path | None, dict]:
    if not repos:
        return {}, None, {"available": False, "reason": "No repository candidates were found."}

    repo = repos[0]
    print(f"[Proposal Agent] Attempting to clone: {repo.get('name')} | clone_url: {repo.get('clone_url')}")
    repo_path = clone_repo(repo)
    repo_inspection = inspect_repo(repo_path)
    if repo_is_useful(repo_inspection) and inspected_repo_score(repo, repo_inspection, research_question) >= 0:
        return repo, repo_path, repo_inspection

    if repo_inspection.get("available"):
        repo_inspection["reason"] = "Top-ranked repository was cloned but did not contain a relevant benchmark."
    return repo, repo_path, repo_inspection


def short_description(text: str, limit: int = 180) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def display_repo(repo: dict) -> dict:
    if not repo:
        return {"status": "NO_REPO_FOUND"}
    return {
        "name": repo.get("name", ""),
        "url": repo.get("url", ""),
        "description": short_description(repo.get("description", "")),
        "stars": repo.get("stars", 0),
        "language": repo.get("language", ""),
        "search_query": repo.get("search_query", ""),
    }


def display_repo_candidates(repos: list[dict], limit: int = 5) -> list[dict]:
    return [display_repo(repo) for repo in repos[:limit]]


def display_repo_inspection(repo_inspection: dict) -> dict:
    if not repo_inspection.get("available"):
        return repo_inspection
    return {
        "available": True,
        "selection_confidence": repo_inspection.get("selection_confidence", "low"),
        "benchmark_file_count": len(repo_inspection.get("benchmark_files", [])),
        "data_file_count": len(repo_inspection.get("repo_data_files", [])),
        "dataset_url_count": len(repo_inspection.get("dataset_urls", [])),
        "data_source_url_count": len(repo_inspection.get("data_source_urls", [])),
        "benchmark_files": repo_inspection.get("benchmark_files", [])[:5],
        "repo_data_files": repo_inspection.get("repo_data_files", [])[:5],
        "data_source_urls": repo_inspection.get("data_source_urls", [])[:5],
        "metrics": repo_inspection.get("metrics", []),
    }


def compact_dataset_choice(dataset_choice: dict) -> dict:
    source = dataset_choice.get("source")
    if isinstance(source, list):
        source_summary = {
            "count": len(source),
            "items": source[:5],
        }
    elif isinstance(source, dict):
        source_summary = source
    else:
        source_summary = source
    return {
        "kind": dataset_choice.get("kind", "unknown"),
        "confidence": dataset_choice.get("confidence", "low"),
        "source": source_summary,
    }


def compact_repo_for_spec(repo: dict) -> dict:
    if not repo:
        return {}
    return {
        "name": repo.get("name", ""),
        "url": repo.get("url", ""),
        "clone_url": repo.get("clone_url", ""),
        "description": short_description(repo.get("description", "")),
        "stars": repo.get("stars", 0),
        "language": repo.get("language", ""),
        "search_query": repo.get("search_query", ""),
    }


def compact_repo_inspection_for_spec(repo_inspection: dict) -> dict:
    if not repo_inspection.get("available"):
        return repo_inspection
    return {
        "available": True,
        "selection_confidence": repo_inspection.get("selection_confidence", "low"),
        "file_count": repo_inspection.get("file_count", 0),
        "benchmark_files": repo_inspection.get("benchmark_files", []),
        "repo_data_files": repo_inspection.get("repo_data_files", []),
        "dataset_urls": repo_inspection.get("dataset_urls", []),
        "data_source_urls": repo_inspection.get("data_source_urls", []),
        "metrics": repo_inspection.get("metrics", []),
    }


def data_file_score(path: str, research_question: str) -> int:
    lowered = path.lower()
    keywords = research_keywords(research_question, 18)
    score = sum(20 for keyword in keywords if keyword in lowered)
    if lowered.endswith((".csv", ".tsv")):
        score += 160
    elif lowered.endswith((".jsonl", ".ndjson")):
        score += 100
    elif lowered.endswith(".json"):
        score += 70
    elif lowered.endswith(".parquet"):
        score += 60
    elif lowered.endswith(".zip"):
        score -= 120
    if "iris" in research_question.lower() and "iris" in lowered:
        score += 250
    if any(term in lowered for term in ("readme", "config", "settings")):
        score -= 80
    return score


def select_data_files(paths: list[str], research_question: str, limit: int = 4) -> list[str]:
    ranked = sorted(
        list(dict.fromkeys(paths)),
        key=lambda item: data_file_score(item, research_question),
        reverse=True,
    )
    return ranked[:limit]


def entrypoint_file_score(path: str, research_question: str) -> int:
    lowered = path.lower().replace("_", " ").replace("-", " ")
    keywords = research_keywords(research_question, 18)
    score = sum(20 for keyword in keywords if keyword in lowered)
    if "random forest" in research_question.lower() and "random" in lowered and "forest" in lowered:
        score += 260
    if "logistic regression" in research_question.lower() and "logistic" in lowered:
        score += 220
    if "iris" in research_question.lower() and "iris" in lowered:
        score += 220
    if "template" in lowered or "untitled" in lowered:
        score -= 90
    if "kernel svm" in lowered and "svm" not in research_question.lower():
        score -= 40
    return score


def select_entrypoints(paths: list[str], research_question: str, limit: int = 6) -> list[str]:
    ranked = sorted(
        list(dict.fromkeys(paths)),
        key=lambda item: entrypoint_file_score(item, research_question),
        reverse=True,
    )
    return ranked[:limit]


def run_proposal_stage(research_question: str, deep_literature_review: str | Path) -> str:
    print("\n[Proposal Agent] Finding benchmark repo and dataset...")
    import shutil
    repos_dir = BENCHMARK_DIR / "repos"
    if repos_dir.exists():
        shutil.rmtree(repos_dir)
        print("[Proposal Agent] Cleared stale repo cache.")
    deep_lit = compact_text(read_text_or_path(deep_literature_review), 1200)
    repos = search_github_repos(research_question)
    hf_datasets = []
    repo, repo_path, repo_inspection = select_and_clone_repo(repos, research_question)
    dataset_choice = choose_dataset_source(repo_inspection, hf_datasets)

    local_dataset_paths = []
    dataset_kind = dataset_choice.get("kind")
    source = dataset_choice.get("source")
    if dataset_kind == "repo_bundled_files" and repo_path and isinstance(source, list):
        local_dataset_paths = [str(repo_path / item) for item in source if (repo_path / item).exists()]
    elif dataset_kind == "repo_direct_downloads" and isinstance(source, list):
        local_dataset_paths = download_dataset_urls(source, BENCHMARK_DIR / "datasets")
    elif isinstance(source, dict) and source.get("repo_dataset_urls"):
        local_dataset_paths = download_dataset_urls(source.get("repo_dataset_urls", []), BENCHMARK_DIR / "datasets")

    hypothesis = make_hypothesis(research_question, repo, repo_inspection, dataset_choice)
    selection_confidence = "high" if dataset_choice.get("confidence") == "high" else repo_inspection.get("selection_confidence", "low")
    selected_entrypoints = select_entrypoints(repo_inspection.get("benchmark_files", []), research_question)
    selected_repo_data_files = select_data_files(repo_inspection.get("repo_data_files", []), research_question)
    selected_local_dataset_paths = select_data_files(local_dataset_paths, research_question)
    compact_dataset = compact_dataset_choice(dataset_choice)
    spec = {
        "runner_type": "BENCHMARK_REPLICATION",
        "research_question": research_question,
        "github_repo": compact_repo_for_spec(repo),
        "local_repo_path": str(repo_path) if repo_path else "TO_CLONE",
        "dataset_choice": compact_dataset,
        "local_dataset_paths": selected_local_dataset_paths,
        "benchmark_entrypoints": selected_entrypoints,
        "repo_data_files": selected_repo_data_files,
        "selection_confidence": selection_confidence,
        "metrics": repo_inspection.get("metrics", []) or ["TO_IDENTIFY_FROM_REPO"],
        "new_hypothesis": hypothesis,
        "execution_policy": "SAFE_INSPECT_ONLY_BY_DEFAULT",
        "notes_for_experiment_agent": (
            "Replicate the cloned repository's benchmark using its existing dataset/variables/metrics. "
            "Do not execute arbitrary repo code unless ALLOW_BENCHMARK_CODE_EXECUTION=true. "
            "If Hugging Face has a clearly stronger matching dataset, use it only when compatible with the repo task."
        ),
    }
    entrypoints = selected_entrypoints
    metrics = repo_inspection.get("metrics", []) or ["TO_IDENTIFY_FROM_REPO"]
    data_sources = {
        "github_repo": repo.get("url") if repo else "TO_FIND",
        "local_repo_path": str(repo_path) if repo_path else "TO_CLONE",
        "dataset_choice": compact_dataset,
        "local_dataset_path_count": len(selected_local_dataset_paths),
        "local_dataset_paths": selected_local_dataset_paths,
        "repo_data_file_count": len(repo_inspection.get("repo_data_files", [])),
        "repo_data_files": selected_repo_data_files,
        "selection_confidence": selection_confidence,
    }
    selected_repo_display = display_repo(repo)
    candidate_display = display_repo_candidates(repos)
    inspection_display = display_repo_inspection(repo_inspection)

    return f"""PROPOSAL SUMMARY
Research question: {research_question}
Selected repo: {selected_repo_display.get("name", "NO_REPO_FOUND")} ({selected_repo_display.get("url", "TO_FIND")})
Confidence: {selection_confidence}
Dataset: {compact_dataset.get("kind")} ({compact_dataset.get("confidence")})
Benchmark files: {len(entrypoints)}
Data files: {len(repo_inspection.get("repo_data_files", []))}
Metrics: {", ".join(metrics)}

RESEARCH QUESTION:
{research_question}

HYPOTHESIS:
{hypothesis}

EXPERIMENT DESIGN:
Replicate the selected benchmark repo, then run a modified comparison using the same dataset, variables, and metrics plus one transparent factor tied to the research question.

PUBLIC DATA SOURCES:
{json.dumps(data_sources, indent=2)}

DATA COLLECTION PLAN:
Use the cloned GitHub repository as the source for benchmark code and bundled or linked data.

METHODOLOGY:
1. Reproduce the original benchmark in an isolated local branch.
2. Preserve the original dataset, variables/features, split, and metrics.
3. Compare the original benchmark against the modified replication.

KEY VARIABLES:
- Independent variables: repository-defined benchmark features plus one transparent added comparison factor.
- Dependent variables: repository-defined benchmark target/outcome.
- Control variables: original dataset, benchmark split, preprocessing, metric definitions, and random seed when available.

SUCCESS CRITERIA:
- The repository is cloned locally and benchmark-relevant scripts are identified.
- The dataset source is local, repository-linked, or a compatible Hugging Face dataset.
- The modified hypothesis comparison reports the same metrics as the original benchmark.

FEASIBILITY CHECK:
Feasible if the selected repository has benchmark scripts and usable data files or data links.

LIMITATIONS AND RISKS:
- GitHub repositories may have stale dependencies, missing data links, hardcoded paths, or GPU requirements.
- Arbitrary repository code is unsafe, so execution is disabled unless ALLOW_BENCHMARK_CODE_EXECUTION=true.

SELECTED GITHUB REPOSITORY:
{json.dumps(selected_repo_display, indent=2)}

REPOSITORY INSPECTION:
{json.dumps(inspection_display, indent=2)}

DATASET DECISION:
{json.dumps(compact_dataset, indent=2)}

METRICS:
{json.dumps(metrics, indent=2)}

EXPERIMENT EXECUTION SPEC:
{json.dumps(spec, indent=2)}
"""


if __name__ == "__main__":
    question = input("Enter selected research question: ")
    review_path = input("Enter deep literature review path or paste text: ")
    print(run_proposal_stage(question, review_path))
