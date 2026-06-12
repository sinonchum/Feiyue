"""Capability promotion and demotion recommendation rules."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Any, Iterable

from pydantic import Field, field_validator

from feiyue_core.capability.performance_record import WorkerTaskResult
from feiyue_core.schemas.common import FeiyueModel


class CapabilityRecommendationAction(StrEnum):
    """Recommended routing/profile action for one model capability level."""

    PROMOTE = "promote"
    KEEP = "keep"
    DEMOTE = "demote"
    ESCALATE_TO_TEACHER = "escalate_to_teacher"


class CapabilityRecommendation(FeiyueModel):
    """Provider-free recommendation emitted by capability evidence rules."""

    recommendation_id: str
    model_id: str
    capability_level: str
    action: CapabilityRecommendationAction
    rationale: str
    source_ids: list[str]

    @field_validator("recommendation_id", "model_id", "capability_level", "rationale")
    @classmethod
    def _validate_required_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be non-empty")
        return stripped

    @field_validator("source_ids")
    @classmethod
    def _validate_source_ids(cls, source_ids: list[str]) -> list[str]:
        if not source_ids:
            raise ValueError("source_ids must contain at least one source id")

        normalized_ids: list[str] = []
        for source_id in source_ids:
            stripped = source_id.strip()
            if not stripped:
                raise ValueError("source_ids must not contain empty source ids")
            normalized_ids.append(stripped)
        return normalized_ids

    def render_markdown(self) -> str:
        """Render deterministic Markdown for the recommendation."""

        return "\n".join(
            [
                f"# Capability Recommendation: {self.recommendation_id}",
                "",
                f"- Model: {self.model_id}",
                f"- Capability Level: {self.capability_level}",
                f"- Action: {self.action.value}",
                "",
                "## Rationale",
                self.rationale,
                "",
                "## Sources",
                *[f"- {source_id}" for source_id in self.source_ids],
            ]
        )


class CapabilityRuleThresholds(FeiyueModel):
    """Tunable thresholds for capability recommendation rules."""

    min_promotion_successes: int = 3
    max_teacher_call_rate_for_promotion: float = 0.0
    max_repeated_mistakes_before_demotion: int = 2

    @field_validator("min_promotion_successes", "max_repeated_mistakes_before_demotion")
    @classmethod
    def _validate_positive_threshold(cls, value: int) -> int:
        if value < 1:
            raise ValueError("threshold must be greater than or equal to 1")
        return value

    @field_validator("max_teacher_call_rate_for_promotion")
    @classmethod
    def _validate_teacher_call_rate(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError("teacher call rate threshold must be between 0.0 and 1.0")
        return value


DEFAULT_CAPABILITY_RULE_THRESHOLDS = CapabilityRuleThresholds()


def evaluate_records_for_capability(
    model_id: str,
    capability_level: str,
    records: Iterable[Any],
    thresholds: CapabilityRuleThresholds = DEFAULT_CAPABILITY_RULE_THRESHOLDS,
) -> CapabilityRecommendation:
    """Evaluate records for one model/capability pair without mutating routing state."""

    normalized_model_id = _non_empty(model_id, "model_id")
    normalized_capability_level = _non_empty(capability_level, "capability_level")
    matching_records = [
        record
        for record in records
        if _record_value(record, "model_id") == normalized_model_id
        and _record_value(record, "capability_level") == normalized_capability_level
    ]

    source_ids = _collect_source_ids(matching_records)
    if not source_ids:
        source_ids = [f"capability-rules:{normalized_model_id}:{normalized_capability_level}"]

    unsafe_records = [
        record for record in matching_records if _result_value(_record_value(record, "result")) == WorkerTaskResult.UNSAFE.value
    ]
    if unsafe_records:
        action = CapabilityRecommendationAction.ESCALATE_TO_TEACHER
        rationale = (
            f"{len(unsafe_records)} unsafe matching record(s) require teacher escalation before routing changes."
        )
        return _recommendation(normalized_model_id, normalized_capability_level, action, rationale, source_ids)

    mistake_counts = Counter(
        mistake
        for record in matching_records
        if (mistake := _optional_string(_record_value(record, "repeated_mistake_category"))) is not None
    )
    repeated_mistake_category: str | None = None
    repeated_mistake_count = 0
    if mistake_counts:
        repeated_mistake_category, repeated_mistake_count = sorted(
            mistake_counts.items(), key=lambda item: (-item[1], item[0])
        )[0]

    passed_count = sum(
        1 for record in matching_records if _result_value(_record_value(record, "result")) == WorkerTaskResult.PASSED.value
    )
    teacher_call_rate = _teacher_call_rate(matching_records)

    if repeated_mistake_count >= thresholds.max_repeated_mistakes_before_demotion:
        action = CapabilityRecommendationAction.DEMOTE
        rationale = (
            f"{repeated_mistake_category} repeated {repeated_mistake_count} time(s), meeting demotion threshold "
            f"{thresholds.max_repeated_mistakes_before_demotion}."
        )
    elif (
        passed_count >= thresholds.min_promotion_successes
        and teacher_call_rate <= thresholds.max_teacher_call_rate_for_promotion
    ):
        action = CapabilityRecommendationAction.PROMOTE
        rationale = (
            f"{len(matching_records)} matching record(s): {passed_count} passed, teacher call rate "
            f"{teacher_call_rate:.2f}, meeting promotion threshold {thresholds.min_promotion_successes}."
        )
    else:
        action = CapabilityRecommendationAction.KEEP
        rationale = (
            f"{len(matching_records)} matching record(s): {passed_count} passed, teacher call rate "
            f"{teacher_call_rate:.2f}, no repeated mistake category reached "
            f"{thresholds.max_repeated_mistakes_before_demotion}."
        )

    return _recommendation(normalized_model_id, normalized_capability_level, action, rationale, source_ids)


def _recommendation(
    model_id: str,
    capability_level: str,
    action: CapabilityRecommendationAction,
    rationale: str,
    source_ids: list[str],
) -> CapabilityRecommendation:
    return CapabilityRecommendation(
        recommendation_id=f"rec-{model_id}-{capability_level}-{action.value}",
        model_id=model_id,
        capability_level=capability_level,
        action=action,
        rationale=rationale,
        source_ids=source_ids,
    )


def _collect_source_ids(records: Iterable[Any]) -> list[str]:
    source_ids: list[str] = []
    seen: set[str] = set()
    for record in records:
        for field_name in ("record_id", "curation_evidence_ids", "review_decision_ids", "source_ids"):
            value = _record_value(record, field_name)
            values = value if isinstance(value, list) else [value]
            for source_id in values:
                if source_id is None:
                    continue
                normalized = str(source_id).strip()
                if normalized and normalized not in seen:
                    source_ids.append(normalized)
                    seen.add(normalized)
    return source_ids


def _teacher_call_rate(records: list[Any]) -> float:
    if not records:
        return 0.0
    records_with_teacher_calls = sum(1 for record in records if int(_record_value(record, "teacher_call_count") or 0) > 0)
    return records_with_teacher_calls / len(records)


def _record_value(record: Any, field_name: str) -> Any:
    if isinstance(record, dict):
        return record.get(field_name)
    return getattr(record, field_name, None)


def _result_value(value: Any) -> str:
    if isinstance(value, WorkerTaskResult):
        return value.value
    return str(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized
