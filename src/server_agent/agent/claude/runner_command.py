"""Normalize patient-level Skill runner commands before execution."""

from __future__ import annotations

import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


VALUE_OPTIONS = (
    "--patient-id",
    "--skill-id",
    "--run-id",
    "--task-slug",
    "--phase",
    "--mode",
    "--model",
    "--mask-role",
    "--label-prompt",
    "--device",
    "--thoracic-start",
    "--thoracic-end",
)
FLAG_OPTIONS = {"--overwrite", "--keep-workspace", "--dry-run"}
SHELL_STOP_TOKENS = {"|", ";", "&&", "||"}


def _normalize_slug(value: str) -> str:
    slug = value.strip().lower().replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "_", slug).strip("_")


def _generated_run_slug(skill_id: str, task_slug: Optional[str], phase: str) -> str:
    slug = _normalize_slug(task_slug or skill_id) or _normalize_slug(skill_id) or "skill_task"
    if phase in {"pre", "post"} and not slug.endswith(f"_{phase}"):
        slug = f"{slug}_{phase}"
    if phase == "both" and (slug.endswith("_pre") or slug.endswith("_post")):
        slug = f"{slug}_both"
    return slug


def ensure_runner_run_id(
    command: str,
    *,
    project_base_dir: Optional[Path] = None,
    generated_run_id: Optional[str] = None,
    now: Callable[[], datetime] = datetime.now,
) -> str:
    """Return a canonical runner command with an independent run_id.

    A missing run_id is generated for this invocation only. PRE and POST runs
    receive distinct phase suffixes required by the Skill wrapper contract.
    """
    if not command:
        return command
    try:
        parts = shlex.split(command)
    except ValueError:
        return command

    runner_index = next(
        (index for index, part in enumerate(parts) if Path(part).name == "run_skill_task.py"),
        None,
    )
    if runner_index is None:
        return command

    previous = parts[runner_index - 1] if runner_index > 0 else ""
    python_executable = previous if Path(previous).name.startswith("python") else "python"
    runner_token = parts[runner_index]
    if not Path(runner_token).is_absolute() and project_base_dir:
        runner_token = str((project_base_dir / runner_token).resolve())

    option_parts: list[str] = []
    for part in parts[runner_index + 1:]:
        if (
            part in SHELL_STOP_TOKENS
            or part.startswith("<")
            or part.startswith(">")
            or ">&" in part
            or part.endswith(">")
        ):
            break
        option_parts.append(part)

    def option_value(name: str) -> Optional[str]:
        for index, part in enumerate(option_parts):
            if part == name and index + 1 < len(option_parts):
                return option_parts[index + 1]
            prefix = f"{name}="
            if part.startswith(prefix):
                return part[len(prefix):]
        return None

    patient_id = option_value("--patient-id")
    skill_id = option_value("--skill-id")
    if not patient_id or not skill_id:
        return command

    normalized = [
        python_executable,
        runner_token,
        "--patient-id",
        patient_id,
        "--skill-id",
        skill_id,
    ]
    for name in VALUE_OPTIONS:
        if name in {"--patient-id", "--skill-id", "--run-id"}:
            continue
        value = option_value(name)
        if value is not None:
            normalized.extend([name, value])

    present_flags = {part for part in option_parts if part in FLAG_OPTIONS}
    for name in sorted(present_flags):
        normalized.append(name)

    run_id = option_value("--run-id") or generated_run_id
    if not run_id:
        phase = option_value("--phase") or "both"
        slug = _generated_run_slug(skill_id, option_value("--task-slug"), phase)
        run_id = f"{now().strftime('%Y%m%d_%H%M%S')}_{slug}"
    normalized.extend(["--run-id", run_id])
    return shlex.join(normalized)


def runner_run_id(command: str) -> Optional[str]:
    """Extract --run-id from a shell command without executing it."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    for index, part in enumerate(parts):
        if part == "--run-id" and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith("--run-id="):
            return part.split("=", 1)[1]
    return None


class RunnerCommandNormalizer:
    """Keep normalization idempotent within one Claude tool invocation."""

    def __init__(
        self,
        *,
        project_base_dir: Optional[Path] = None,
        now: Callable[[], datetime] = datetime.now,
    ):
        self._project_base_dir = project_base_dir
        self._now = now
        self._tool_run_ids: dict[str, str] = {}

    def normalize(self, command: str, tool_use_id: Optional[object] = None) -> str:
        key = str(tool_use_id) if tool_use_id else None
        explicit_run_id = runner_run_id(command)
        cached_run_id = self._tool_run_ids.get(key) if key else None
        normalized = ensure_runner_run_id(
            command,
            project_base_dir=self._project_base_dir,
            generated_run_id=explicit_run_id or cached_run_id,
            now=self._now,
        )
        normalized_run_id = runner_run_id(normalized)
        if key and normalized_run_id:
            self._tool_run_ids[key] = normalized_run_id
        return normalized

    def forget(self, tool_use_id: Optional[object]) -> None:
        if tool_use_id:
            self._tool_run_ids.pop(str(tool_use_id), None)

    def clear(self) -> None:
        self._tool_run_ids.clear()
