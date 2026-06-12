from __future__ import annotations

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel

DEFAULT_MAX_ERROR_CHARS = 2000


class BugDossier(FeiyueModel):
    """Structured handoff describing a blocked task and its failure context."""

    task_id: str
    original_task: str
    changed_files: list[str] = Field(default_factory=list)
    failing_command: str
    error_excerpt: str
    attempts: list[str] = Field(default_factory=list)
    suspected_cause: str
    teacher_request: str

    def render_markdown(self, *, max_error_chars: int = DEFAULT_MAX_ERROR_CHARS) -> str:
        """Render a deterministic Markdown dossier safe for teacher review."""
        error_excerpt = _truncate_text(self.error_excerpt, max_error_chars)
        lines = [
            "# Bug Dossier",
            "",
            "## Task ID",
            self.task_id,
            "",
            "## Original Task",
            self.original_task,
            "",
            "## Changed Files",
            *_render_list(self.changed_files),
            "",
            "## Failing Command",
            f"`{self.failing_command}`",
            "",
            "## Error Excerpt",
            "```",
            error_excerpt,
            "```",
            "",
            "## Attempts",
            *_render_list(self.attempts),
            "",
            "## Suspected Cause",
            self.suspected_cause,
            "",
            "## Request to Teacher",
            self.teacher_request,
        ]
        return "\n".join(lines)


def _render_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _truncate_text(value: str, max_chars: int) -> str:
    if max_chars < 0:
        raise ValueError("max_error_chars must be non-negative")
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"{value[:max_chars]}... [truncated {omitted} chars]"
