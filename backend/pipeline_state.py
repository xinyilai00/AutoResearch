from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from backend.repo_library import RepoMetadata, select_repo_for_prompt
except ImportError:
    from repo_library import RepoMetadata, select_repo_for_prompt

# ── Experiment Anchor ──────────────────────────────────────────────────────────
# Set dynamically from the user's prompt before stage agents run.

_EXPERIMENT_REPO_URL: str = ""
_EXPERIMENT_REPO_ID: str = ""
_EXPERIMENT_REPO_NAME: str = ""
_EXPERIMENT_HYPOTHESIS: str = ""


def generate_hypothesis_from_repo(prompt: str, repo: RepoMetadata) -> str:
    return (
        f"Using {repo['name']}, this study investigates the following: "
        f"{prompt.strip()}."
    )


def set_experiment_anchor(repo_url: str, hypothesis: str, repo_id: str = "custom", repo_name: str = "custom") -> None:
    global _EXPERIMENT_REPO_URL, _EXPERIMENT_HYPOTHESIS, _EXPERIMENT_REPO_ID, _EXPERIMENT_REPO_NAME
    _EXPERIMENT_REPO_URL = repo_url
    _EXPERIMENT_HYPOTHESIS = hypothesis
    _EXPERIMENT_REPO_ID = repo_id
    _EXPERIMENT_REPO_NAME = repo_name


def configure_experiment_anchor_from_prompt(prompt: str) -> dict:
    selected_repo = select_repo_for_prompt(prompt)
    hypothesis = generate_hypothesis_from_repo(prompt, selected_repo)
    set_experiment_anchor(
        selected_repo["url"],
        hypothesis,
        repo_id=selected_repo["id"],
        repo_name=selected_repo["name"],
    )
    return get_experiment_anchor()


def get_experiment_anchor() -> dict:
    if not _EXPERIMENT_REPO_URL or not _EXPERIMENT_HYPOTHESIS:
        configure_experiment_anchor_from_prompt("general benchmark study")

    return {
        "repo_id": _EXPERIMENT_REPO_ID,
        "repo_name": _EXPERIMENT_REPO_NAME,
        "repo_url": _EXPERIMENT_REPO_URL,
        "hypothesis": _EXPERIMENT_HYPOTHESIS,
    }

DEFAULT_RUN_DIR = Path("paper_runs/latest")


class PipelineState:
    def __init__(self, run_dir: str | Path = DEFAULT_RUN_DIR):
        self.run_dir = Path(run_dir)
        self.state_path = self.run_dir / "run_state.json"
        self.stage_dir = self.run_dir / "stage_outputs"
        self.internal_dir = self.run_dir / ".internal"
        self.output_store_path = self.internal_dir / "stage_outputs.json"
        self.feedback_dir = self.run_dir / "feedback"
        self.state = self._load()
        self.output_store = self._load_output_store()

    def _load(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "active_outputs": {},
            "stage_status": {},
            "versions": {},
            "feedback": {},
            "metadata": {},
        }

    def _load_output_store(self) -> dict[str, Any]:
        if self.output_store_path.exists():
            return json.loads(self.output_store_path.read_text(encoding="utf-8"))
        return {}

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def save_output_store(self) -> None:
        self.output_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_store_path.write_text(json.dumps(self.output_store, indent=2), encoding="utf-8")

    def set_metadata(self, key: str, value: Any) -> None:
        self.state.setdefault("metadata", {})[key] = value
        self.save()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.state.get("metadata", {}).get(key, default)

    def write_stage_files_enabled(self) -> bool:
        return os.getenv("WRITE_STAGE_OUTPUT_FILES", "").lower() == "true"

    def write_stage_output(self, stage: str, text: str, status: str = "generated") -> Path:
        version = len(self.state.setdefault("versions", {}).setdefault(stage, [])) + 1
        versioned_path = self.stage_dir / f"{stage}_output_v{version:02d}.md"
        latest_path = self.stage_dir / f"{stage}_output.md"

        clean_text = text.rstrip() + "\n"
        self.output_store.setdefault(stage, []).append(
            {
                "version": version,
                "text": clean_text,
                "status": status,
            }
        )
        self.save_output_store()

        if self.write_stage_files_enabled():
            self.stage_dir.mkdir(parents=True, exist_ok=True)
            versioned_path.write_text(clean_text, encoding="utf-8")
            latest_path.write_text(clean_text, encoding="utf-8")
            active_ref = str(versioned_path)
        else:
            active_ref = f"internal://stage_outputs/{stage}/v{version:02d}"

        version_record = {
            "version": version,
            "path": active_ref,
            "status": status,
        }
        self.state["versions"][stage].append(version_record)
        self.state.setdefault("active_outputs", {})[stage] = active_ref
        self.state.setdefault("stage_status", {})[stage] = status
        self.save()
        return versioned_path if self.write_stage_files_enabled() else Path(active_ref)

    def write_feedback(self, stage: str, feedback_text: str) -> Path:
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        version = len(self.state.setdefault("feedback", {}).setdefault(stage, [])) + 1
        feedback_path = self.feedback_dir / f"{stage}_feedback_{version:02d}.md"
        feedback_path.write_text(feedback_text.rstrip() + "\n", encoding="utf-8")

        self.state["feedback"][stage].append(
            {
                "version": version,
                "path": str(feedback_path),
            }
        )
        self.state.setdefault("stage_status", {})[stage] = "needs_revision"
        self.save()
        return feedback_path

    def active_path(self, stage: str) -> Path | None:
        path = self.state.get("active_outputs", {}).get(stage)
        if path and str(path).startswith("internal://"):
            return None
        return Path(path) if path else None

    def read_active_output(self, stage: str) -> str:
        ref = self.state.get("active_outputs", {}).get(stage)
        if ref and str(ref).startswith("internal://"):
            versions = self.output_store.get(stage, [])
            return str(versions[-1].get("text", "")) if versions else ""

        path = self.active_path(stage)
        if path and path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def approve_stage(self, stage: str) -> None:
        self.state.setdefault("stage_status", {})[stage] = "approved"
        self.save()

    def set_stage_status(self, stage: str, status: str) -> None:
        self.state.setdefault("stage_status", {})[stage] = status
        self.save()


def compose_feedback_prompt(
    *,
    original_input: str,
    previous_output: str,
    feedback: str,
    instruction: str,
) -> str:
    return (
        f"{original_input.rstrip()}\n\n"
        "Previous stage output:\n"
        f"{previous_output.rstrip()}\n\n"
        "User feedback for revision:\n"
        f"{feedback.rstrip()}\n\n"
        f"{instruction.rstrip()}\n"
    )
