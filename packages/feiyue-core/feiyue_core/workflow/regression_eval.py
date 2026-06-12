from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.lesson_packet import LessonPacket


class UnsafeRegressionCommandError(ValueError):
    """Raised when a lesson verifier is not safe to run as a regression check."""


class RegressionCheck(FeiyueModel):
    """A low-risk command that can be run to guard against a known regression."""

    check_id: str
    description: str
    command: str
    source_lesson_id: str


@dataclass(frozen=True)
class RegressionEvalAssets:
    """Paths written by RegressionEvalWriter."""

    forbidden_patterns_path: Path
    regression_checks_path: Path


_SAFE_COMMAND_PREFIXES = (
    "grep",
    "rg",
    "python -m pytest",
    "npm test",
    "npm run typecheck",
    "git diff --check",
)

_UNSAFE_COMMAND_PREFIXES = (
    "rm",
    "mv",
    "cp",
    "git push",
    "git commit",
    "curl",
    "chmod",
)

_UNSAFE_COMMAND_FRAGMENTS = (
    "sed -i",
    "| sh",
    "| bash",
    ">",
    "<",
    "&& rm",
    "; rm",
)


def build_regression_check_from_lesson(lesson: LessonPacket) -> RegressionCheck:
    """Build a safe, deterministic regression check from a lesson packet."""

    command = lesson.verifier.strip()
    _validate_safe_command(command)
    description = (
        f"Regression guard for lesson {lesson.lesson_id}. "
        f"Trigger: {lesson.trigger} Prevention: {lesson.prevention_prompt_rule}"
    )
    return RegressionCheck(
        check_id=lesson.lesson_id,
        description=description,
        command=command,
        source_lesson_id=lesson.lesson_id,
    )


class RegressionEvalWriter:
    """Write regression evaluation assets under .hermes/evals."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.eval_dir = self.project_root / ".hermes" / "evals"
        self.forbidden_patterns_path = self.eval_dir / "forbidden-patterns.txt"
        self.regression_checks_path = self.eval_dir / "regression-checks.sh"

    def write(
        self, checks: list[RegressionCheck], *, overwrite: bool = False
    ) -> RegressionEvalAssets:
        """Write deterministic eval assets, preserving existing files by default."""

        ordered_checks = sorted(checks, key=lambda check: (check.check_id, check.command))
        self.eval_dir.mkdir(parents=True, exist_ok=True)

        if overwrite or not self.forbidden_patterns_path.exists():
            self.forbidden_patterns_path.write_text(
                _render_forbidden_patterns(ordered_checks), encoding="utf-8"
            )

        if overwrite or not self.regression_checks_path.exists():
            self.regression_checks_path.write_text(
                _render_regression_script(ordered_checks), encoding="utf-8"
            )
            self.regression_checks_path.chmod(0o755)

        return RegressionEvalAssets(
            forbidden_patterns_path=self.forbidden_patterns_path,
            regression_checks_path=self.regression_checks_path,
        )


def _validate_safe_command(command: str) -> None:
    lowered = command.lower()
    if not command:
        raise UnsafeRegressionCommandError("Regression command must not be empty.")

    for prefix in _UNSAFE_COMMAND_PREFIXES:
        if lowered == prefix or lowered.startswith(f"{prefix} "):
            raise UnsafeRegressionCommandError(
                f"Unsafe regression command rejected: {command}"
            )

    for fragment in _UNSAFE_COMMAND_FRAGMENTS:
        if fragment in lowered:
            raise UnsafeRegressionCommandError(
                f"Unsafe regression command rejected: {command}"
            )

    if not any(
        lowered == prefix or lowered.startswith(f"{prefix} ")
        for prefix in _SAFE_COMMAND_PREFIXES
    ):
        raise UnsafeRegressionCommandError(
            f"Regression command is not in the safe allowlist: {command}"
        )


def _render_forbidden_patterns(checks: list[RegressionCheck]) -> str:
    lines = ["# Regression forbidden patterns", ""]
    for index, check in enumerate(checks):
        lines.extend(
            [
                f"## {check.source_lesson_id}",
                f"trigger: {_extract_description_part(check.description, 'Trigger')}",
                f"prevention: {_extract_description_part(check.description, 'Prevention')}",
                f"command: {check.command}",
            ]
        )
        if index != len(checks) - 1:
            lines.append("")
    return "\n".join(lines) + "\n"


def _render_regression_script(checks: list[RegressionCheck]) -> str:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for index, check in enumerate(checks):
        lines.extend(
            [
                f"echo 'Running regression check {_shell_single_quote_safe(check.check_id)}'",
                check.command,
            ]
        )
        if index != len(checks) - 1:
            lines.append("")
    return "\n".join(lines) + "\n"


def _extract_description_part(description: str, label: str) -> str:
    marker = f"{label}: "
    start = description.find(marker)
    if start == -1:
        return description
    start += len(marker)
    next_marker = " Prevention: " if label == "Trigger" else ""
    if next_marker:
        end = description.find(next_marker, start)
        if end != -1:
            return description[start:end]
    return description[start:]


def _shell_single_quote_safe(value: str) -> str:
    return value.replace("'", "'\\''")
