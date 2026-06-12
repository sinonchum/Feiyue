from __future__ import annotations

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class LessonPacket(FeiyueModel):
    """Structured lesson extracted from a task failure or teacher intervention."""

    lesson_id: str
    project: str
    trigger: str
    root_cause: str
    prevention_prompt_rule: str
    verifier: str
    skill_patch_suggestion: str
    applies_to: list[str] = Field(default_factory=list)
    source_task_id: str

    def render_markdown(self) -> str:
        """Render a deterministic Markdown lesson packet."""
        lines = [
            f"# Lesson Packet: {self.lesson_id}",
            "",
            "## Project",
            self.project,
            "",
            "## Trigger",
            self.trigger,
            "",
            "## Root Cause",
            self.root_cause,
            "",
            "## Prevention",
            f"**Prompt Rule:** {self.prevention_prompt_rule}",
            "",
            f"**Verifier:** `{self.verifier}`",
            "",
            f"**Skill Patch Suggestion:** {self.skill_patch_suggestion}",
            "",
            "## Applies To",
            *_render_list(self.applies_to),
            "",
            "## Source Task",
            self.source_task_id,
        ]
        return "\n".join(lines)


def _render_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]
