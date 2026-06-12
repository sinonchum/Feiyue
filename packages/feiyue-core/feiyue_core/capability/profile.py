"""Model capability profile aggregation contracts."""

from __future__ import annotations

from collections import Counter

from pydantic import Field, field_validator

from feiyue_core.capability.performance_record import (
    WorkerPerformanceRecord,
    WorkerTaskResult,
)
from feiyue_core.schemas.common import FeiyueModel


class CapabilityLevelStats(FeiyueModel):
    """Aggregated performance statistics for one model at one capability level."""

    model_id: str
    capability_level: str
    total: int
    passed: int
    failed: int
    blocked: int
    unsafe: int
    teacher_call_total: int
    repeated_mistake_counts: dict[str, int] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    review_decision_ids: list[str] = Field(default_factory=list)

    @field_validator(
        "total",
        "passed",
        "failed",
        "blocked",
        "unsafe",
        "teacher_call_total",
    )
    @classmethod
    def _validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("count fields must be non-negative")
        return value

    @field_validator("repeated_mistake_counts")
    @classmethod
    def _validate_repeated_mistake_counts(cls, value: dict[str, int]) -> dict[str, int]:
        for category, count in value.items():
            if not category.strip():
                raise ValueError("repeated_mistake_counts keys must be non-empty")
            if count < 0:
                raise ValueError("repeated_mistake_counts values must be non-negative")
        return value

    @property
    def pass_rate(self) -> float:
        """Return passed / total, or 0.0 when no records are present."""

        if self.total == 0:
            return 0.0
        return self.passed / self.total

    @property
    def teacher_call_rate(self) -> float:
        """Return teacher_call_total / total, or 0.0 when no records are present."""

        if self.total == 0:
            return 0.0
        return self.teacher_call_total / self.total

    def render_markdown(self) -> str:
        """Render a deterministic Markdown summary for these level stats."""

        lines = [
            f"## Capability Level: {self.capability_level}",
            "",
            f"- Model: {self.model_id}",
            f"- Total: {self.total}",
            f"- Passed: {self.passed}",
            f"- Failed: {self.failed}",
            f"- Blocked: {self.blocked}",
            f"- Unsafe: {self.unsafe}",
            f"- Pass Rate: {self.pass_rate:.4f}",
            f"- Teacher Calls: {self.teacher_call_total}",
            f"- Teacher Call Rate: {self.teacher_call_rate:.4f}",
            "",
            "**Repeated Mistakes:**",
            *_render_count_map(self.repeated_mistake_counts),
            "",
            "**Evidence IDs:**",
            *_render_list(self.evidence_ids),
            "",
            "**Review Decision IDs:**",
            *_render_list(self.review_decision_ids),
        ]
        return "\n".join(lines)


class ModelCapabilityProfile(FeiyueModel):
    """Aggregated capability profile for one model."""

    model_id: str
    stats_by_level: dict[str, CapabilityLevelStats] = Field(default_factory=dict)

    def render_markdown(self) -> str:
        """Render deterministic Markdown for the model capability profile."""

        lines = [f"# Model Capability Profile: {self.model_id}"]
        for level in sorted(self.stats_by_level):
            lines.extend(["", self.stats_by_level[level].render_markdown()])
        return "\n".join(lines)


def build_model_capability_profile(
    model_id: str, records: list[WorkerPerformanceRecord]
) -> ModelCapabilityProfile:
    """Build a provider-free model capability profile from performance records."""

    builders: dict[str, _StatsBuilder] = {}
    for record in records:
        if record.model_id != model_id:
            continue

        builder = builders.setdefault(record.capability_level, _StatsBuilder(model_id, record.capability_level))
        builder.add(record)

    return ModelCapabilityProfile(
        model_id=model_id,
        stats_by_level={level: builders[level].build() for level in sorted(builders)},
    )


class _StatsBuilder:
    def __init__(self, model_id: str, capability_level: str) -> None:
        self.model_id = model_id
        self.capability_level = capability_level
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.blocked = 0
        self.unsafe = 0
        self.teacher_call_total = 0
        self.repeated_mistake_counts: Counter[str] = Counter()
        self.evidence_ids: list[str] = []
        self.review_decision_ids: list[str] = []

    def add(self, record: WorkerPerformanceRecord) -> None:
        self.total += 1
        if record.result is WorkerTaskResult.PASSED:
            self.passed += 1
        elif record.result is WorkerTaskResult.FAILED:
            self.failed += 1
        elif record.result is WorkerTaskResult.BLOCKED:
            self.blocked += 1
        elif record.result is WorkerTaskResult.UNSAFE:
            self.unsafe += 1

        self.teacher_call_total += record.teacher_call_count
        if record.repeated_mistake_category is not None:
            self.repeated_mistake_counts[record.repeated_mistake_category] += 1

        _extend_unique(
            self.evidence_ids,
            [record.record_id, *record.curation_evidence_ids, *record.source_ids],
        )
        _extend_unique(self.review_decision_ids, record.review_decision_ids)

    def build(self) -> CapabilityLevelStats:
        return CapabilityLevelStats(
            model_id=self.model_id,
            capability_level=self.capability_level,
            total=self.total,
            passed=self.passed,
            failed=self.failed,
            blocked=self.blocked,
            unsafe=self.unsafe,
            teacher_call_total=self.teacher_call_total,
            repeated_mistake_counts=dict(sorted(self.repeated_mistake_counts.items())),
            evidence_ids=self.evidence_ids,
            review_decision_ids=self.review_decision_ids,
        )


def _extend_unique(target: list[str], values: list[str]) -> None:
    seen = set(target)
    for value in values:
        if value not in seen:
            target.append(value)
            seen.add(value)


def _render_count_map(values: dict[str, int]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {key}: {values[key]}" for key in sorted(values)]


def _render_list(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {value}" for value in values]
