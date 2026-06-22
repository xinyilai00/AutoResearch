from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_RUN_DIR = Path("paper_runs/latest")


class PipelineState:
    def __init__(self, run_dir: str | Path = DEFAULT_RUN_DIR):
        self.run_dir = Path(run_dir)
        self.state_path = self.run_dir / "run_state.json"
        self.stage_dir = self.run_dir / "stage_outputs"
        self.feedback_dir = self.run_dir / "feedback"
        self.state = self._load()

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

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def set_metadata(self, key: str, value: Any) -> None:
        self.state.setdefault("metadata", {})[key] = value
        self.save()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.state.get("metadata", {}).get(key, default)

    def write_stage_output(self, stage: str, text: str, status: str = "generated") -> Path:
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        version = len(self.state.setdefault("versions", {}).setdefault(stage, [])) + 1
        versioned_path = self.stage_dir / f"{stage}_output_v{version:02d}.md"
        latest_path = self.stage_dir / f"{stage}_output.md"

        clean_text = text.rstrip() + "\n"
        versioned_path.write_text(clean_text, encoding="utf-8")
        latest_path.write_text(clean_text, encoding="utf-8")

        version_record = {
            "version": version,
            "path": str(versioned_path),
            "status": status,
        }
        self.state["versions"][stage].append(version_record)
        self.state.setdefault("active_outputs", {})[stage] = str(versioned_path)
        self.state.setdefault("stage_status", {})[stage] = status
        self.save()
        return versioned_path

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
        return Path(path) if path else None

    def read_active_output(self, stage: str) -> str:
        path = self.active_path(stage)
        if not path or not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

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
