from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


def _string_list(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return [str(value) for value in values]


def _metadata_list(metadata: dict[str, Any], key: str) -> list[str]:
    return _string_list(metadata.get(key, []))


def _render_list(items: list[str], *, code: bool = False) -> str:
    if not items:
        return "- None"
    if code:
        return "\n".join(f"- `{item}`" for item in items)
    return "\n".join(f"- {item}" for item in items)


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    title: str
    scope: str
    files_to_modify: list[str] = field(default_factory=list)
    files_not_to_touch: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    escalation_rule: str = ""

    @classmethod
    def from_task_spec(cls, task_spec: Any) -> "TaskContract":
        """Build a contract from the stable public TaskSpec-like fields.

        This method is intentionally duck-typed to avoid coupling workflow rendering to
        a specific TaskSpec implementation while lanes evolve in parallel. Additional
        contract fields are read from task_spec.metadata when present.
        """

        metadata = getattr(task_spec, "metadata", {}) or {}
        return cls(
            task_id=str(getattr(task_spec, "id")),
            title=str(getattr(task_spec, "title")),
            scope=str(getattr(task_spec, "goal", metadata.get("scope", ""))),
            files_to_modify=_metadata_list(metadata, "files_to_modify"),
            files_not_to_touch=_metadata_list(metadata, "files_not_to_touch"),
            context=_metadata_list(metadata, "context"),
            requirements=_metadata_list(metadata, "requirements"),
            acceptance_criteria=_string_list(getattr(task_spec, "acceptance_criteria", [])),
            verification_commands=_metadata_list(metadata, "verification_commands"),
            escalation_rule=str(metadata.get("escalation_rule", "")),
        )

    def render_markdown(self) -> str:
        sections = [
            f"# Task Contract: {self.title}",
            "## Task ID\n" + self.task_id,
            "## Scope\n" + self.scope,
            "## Files to Modify\n" + _render_list(self.files_to_modify),
            "## Files Not to Touch\n" + _render_list(self.files_not_to_touch),
            "## Context\n" + _render_list(self.context),
            "## Requirements\n" + _render_list(self.requirements),
            "## Acceptance Criteria\n" + _render_list(self.acceptance_criteria),
            "## Verification Commands\n" + _render_list(self.verification_commands, code=True),
            "## Escalation Rule\n" + self.escalation_rule,
        ]
        return "\n\n".join(sections) + "\n"


def build_task_contract(
    *,
    task_id: str,
    title: str,
    scope: str,
    files_to_modify: Iterable[Any] | None = None,
    files_not_to_touch: Iterable[Any] | None = None,
    context: Iterable[Any] | None = None,
    requirements: Iterable[Any] | None = None,
    acceptance_criteria: Iterable[Any] | None = None,
    verification_commands: Iterable[Any] | None = None,
    escalation_rule: str = "",
) -> TaskContract:
    return TaskContract(
        task_id=str(task_id),
        title=str(title),
        scope=str(scope),
        files_to_modify=_string_list(files_to_modify),
        files_not_to_touch=_string_list(files_not_to_touch),
        context=_string_list(context),
        requirements=_string_list(requirements),
        acceptance_criteria=_string_list(acceptance_criteria),
        verification_commands=_string_list(verification_commands),
        escalation_rule=str(escalation_rule),
    )
