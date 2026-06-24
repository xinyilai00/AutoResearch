from __future__ import annotations

import os
from pathlib import Path

try:
    from ..config import PRINCIPAL_ID
    from ..experiment_agent import (
        dataset_urls_from_spec,
        looks_like_csv_url,
        looks_like_supported_data_file,
    )
except ImportError:
    from config import PRINCIPAL_ID
    from experiment_agent import (
        dataset_urls_from_spec,
        looks_like_csv_url,
        looks_like_supported_data_file,
    )


EXPERIMENT_PRINCIPAL_ID = os.getenv("EXPERIMENT_PRINCIPAL_ID", PRINCIPAL_ID)


def run_data_agent(spec: dict, proposal: str = "") -> dict:
    runner_type = str(spec.get("runner_type", "")).lower()
    urls = dataset_urls_from_spec(spec)
    usable_urls = []
    issues = []

    if not urls:
        issues.append("No dataset_url or dataset_urls were provided.")

    for url in urls:
        upper = url.upper()
        if upper == "TO_VERIFY":
            issues.append("Dataset URL is TO_VERIFY.")
            continue
        if Path(url).exists():
            usable_urls.append(url)
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            issues.append(f"Dataset location is not HTTP(S) or an existing local path: {url}")
            continue
        if runner_type in {"universal_tabular_csv", "direct_csv", "multi_csv"}:
            if looks_like_csv_url(url):
                usable_urls.append(url)
            else:
                issues.append(f"CSV runner requires a direct .csv URL: {url}")
        elif runner_type == "universal_data_file":
            if looks_like_supported_data_file(url):
                usable_urls.append(url)
            else:
                issues.append(f"universal_data_file cannot read this URL type: {url}")
        else:
            usable_urls.append(url)

    return {
        "agent": "data",
        "principal_id": EXPERIMENT_PRINCIPAL_ID,
        "dataset_urls": urls,
        "usable_urls": usable_urls,
        "issues": issues,
        "ready": bool(usable_urls) and not any("TO_VERIFY" in issue for issue in issues),
    }
