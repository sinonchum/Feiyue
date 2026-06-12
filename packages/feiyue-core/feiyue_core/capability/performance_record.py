"""Worker performance record capability contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkerTaskResult(StrEnum):
    """Verifier-visible outcome for a worker task attempt."""

    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNSAFE = "unsafe"


class WorkerPerformanceRecord(BaseModel):
    """Provider-free record of worker task performance evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    record_id: str
    worker_id: str
    model_id: str
    task_id: str
    capability_level: str
    result: WorkerTaskResult
    verifier_result: str
    teacher_call_count: int = 0
    repeated_mistake_category: str | None = None
    curation_evidence_ids: list[str]
    review_decision_ids: list[str] = Field(default_factory=list)
    source_ids: list[str]

    @field_validator(
        "record_id",
        "worker_id",
        "model_id",
        "task_id",
        "capability_level",
        "verifier_result",
        "repeated_mistake_category",
        mode="before",
    )
    @classmethod
    def _strip_optional_and_required_strings(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must be non-empty")
            return stripped
        return value

    @field_validator("teacher_call_count")
    @classmethod
    def _validate_teacher_call_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("teacher_call_count must be greater than or equal to 0")
        return value

    @field_validator("curation_evidence_ids", "review_decision_ids", "source_ids")
    @classmethod
    def _validate_id_lists(cls, value: list[str], info: Any) -> list[str]:
        if info.field_name in {"curation_evidence_ids", "source_ids"} and not value:
            raise ValueError(f"{info.field_name} must be non-empty")

        normalized_ids: list[str] = []
        for identifier in value:
            if not isinstance(identifier, str):
                raise TypeError(f"{info.field_name} entries must be strings")
            stripped = identifier.strip()
            if not stripped:
                raise ValueError(f"{info.field_name} entries must be non-empty")
            normalized_ids.append(stripped)
        return normalized_ids

    @property
    def is_successful_without_teacher(self) -> bool:
        """Return true when the worker passed without teacher intervention."""

        return self.result is WorkerTaskResult.PASSED and self.teacher_call_count == 0

    def render_markdown(self) -> str:
        """Render a deterministic markdown summary of the record."""

        return "\n".join(
            [
                f"# Worker Performance Record: {self.record_id}",
                "",
                f"- Worker: {self.worker_id}",
                f"- Model: {self.model_id}",
                f"- Task: {self.task_id}",
                f"- Capability Level: {self.capability_level}",
                f"- Result: {self.result.value}",
                f"- Verifier Result: {self.verifier_result}",
                f"- Teacher Calls: {self.teacher_call_count}",
                f"- Repeated Mistake Category: {_render_optional(self.repeated_mistake_category)}",
                f"- Curation Evidence IDs: {_render_ids(self.curation_evidence_ids)}",
                f"- Review Decision IDs: {_render_ids(self.review_decision_ids)}",
                f"- Source IDs: {_render_ids(self.source_ids)}",
            ]
        ) + "\n"


def _render_optional(value: str | None) -> str:
    return value if value is not None else "None"


def _render_ids(values: list[str]) -> str:
    return ", ".join(values) if values else "None"
