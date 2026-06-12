"""Strategy evaluation record contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, field_validator


class StrategyOutcome(StrEnum):
    """Evaluation outcome for a strategy attempt."""

    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNSAFE = "unsafe"


class CreativeAcceptanceStatus(StrEnum):
    """Creative acceptance status associated with an evaluated strategy."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"


class StrategyEvaluationRecord(BaseModel):
    """Provider-free record of strategy evaluation evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    record_id: str
    strategy_id: str
    model_id: str
    task_id: str
    capability_level: str
    outcome: StrategyOutcome
    teacher_call_count: int = 0
    cost_units: float = 0.0
    latency_units: float = 0.0
    creative_acceptance_status: CreativeAcceptanceStatus = CreativeAcceptanceStatus.NOT_APPLICABLE
    source_ids: list[str]

    @field_validator(
        "record_id",
        "strategy_id",
        "model_id",
        "task_id",
        "capability_level",
        mode="before",
    )
    @classmethod
    def _strip_and_validate_required_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must be non-empty")
            return stripped
        return value

    @field_validator("teacher_call_count", "cost_units", "latency_units")
    @classmethod
    def _validate_non_negative_number(cls, value: int | float, info: Any) -> int | float:
        if value < 0:
            raise ValueError(f"{info.field_name} must be greater than or equal to 0")
        return value

    @field_validator("source_ids")
    @classmethod
    def _validate_source_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("source_ids must be non-empty")

        normalized_ids: list[str] = []
        for identifier in value:
            if not isinstance(identifier, str):
                raise TypeError("source_ids entries must be strings")
            stripped = identifier.strip()
            if not stripped:
                raise ValueError("source_ids entries must be non-empty")
            normalized_ids.append(stripped)
        return normalized_ids

    def render_markdown(self) -> str:
        """Render a deterministic markdown summary of the record."""

        return "\n".join(
            [
                f"# Strategy Evaluation Record: {self.record_id}",
                "",
                f"- Strategy: {self.strategy_id}",
                f"- Model: {self.model_id}",
                f"- Task: {self.task_id}",
                f"- Capability Level: {self.capability_level}",
                f"- Outcome: {self.outcome.value}",
                f"- Teacher Calls: {self.teacher_call_count}",
                f"- Cost Units: {self.cost_units:g}",
                f"- Latency Units: {self.latency_units:g}",
                f"- Creative Acceptance Status: {self.creative_acceptance_status.value}",
                f"- Source IDs: {_render_ids(self.source_ids)}",
            ]
        ) + "\n"


def _render_ids(values: list[str]) -> str:
    return ", ".join(values)
