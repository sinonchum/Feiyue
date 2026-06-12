"""Strategy scorecard aggregation for Feiyue evaluation records."""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel


class StrategyScorecard(FeiyueModel):
    """Provider-free aggregate metrics for one strategy."""

    strategy_id: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    blocked: int = Field(ge=0)
    unsafe: int = Field(ge=0)
    teacher_call_total: int = Field(ge=0)
    cost_total: float = Field(ge=0.0)
    latency_total: float = Field(ge=0.0)
    creative_accepted: int = Field(ge=0)
    creative_rejected: int = Field(ge=0)
    creative_deferred: int = Field(ge=0)
    source_ids: list[str]

    @field_validator("strategy_id")
    @classmethod
    def _validate_strategy_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("strategy_id must be non-empty")
        return normalized

    @field_validator("source_ids")
    @classmethod
    def _validate_source_ids(cls, source_ids: list[str]) -> list[str]:
        if not source_ids:
            raise ValueError("source_ids must contain at least one source id")

        normalized_ids: list[str] = []
        for source_id in source_ids:
            normalized = str(source_id).strip()
            if not normalized:
                raise ValueError("source_ids must not contain empty source ids")
            normalized_ids.append(normalized)
        return normalized_ids

    @property
    def pass_rate(self) -> float:
        """Share of matching records whose outcome passed."""

        if self.total == 0:
            return 0.0
        return self.passed / self.total

    @property
    def teacher_call_rate(self) -> float:
        """Average teacher calls per matching record."""

        if self.total == 0:
            return 0.0
        return self.teacher_call_total / self.total

    @property
    def average_cost(self) -> float:
        """Average cost units per matching record."""

        if self.total == 0:
            return 0.0
        return self.cost_total / self.total

    @property
    def average_latency(self) -> float:
        """Average latency units per matching record."""

        if self.total == 0:
            return 0.0
        return self.latency_total / self.total

    @property
    def accepted_creative_rate(self) -> float:
        """Share of explicit creative decisions that were accepted."""

        creative_total = self.creative_accepted + self.creative_rejected + self.creative_deferred
        if creative_total == 0:
            return 0.0
        return self.creative_accepted / creative_total

    def render_markdown(self) -> str:
        """Render deterministic Markdown for the scorecard."""

        return "\n".join(
            [
                f"# Strategy Scorecard: {self.strategy_id}",
                "",
                f"- Total Records: {self.total}",
                (
                    f"- Outcomes: {self.passed} passed, {self.failed} failed, "
                    f"{self.blocked} blocked, {self.unsafe} unsafe"
                ),
                f"- Pass Rate: {self.pass_rate:.2f}",
                f"- Teacher Calls: {self.teacher_call_total} total, rate {self.teacher_call_rate:.2f}",
                f"- Cost: {self.cost_total:.2f} total, average {self.average_cost:.2f}",
                f"- Latency: {self.latency_total:.2f} total, average {self.average_latency:.2f}",
                (
                    f"- Creative Decisions: {self.creative_accepted} accepted, "
                    f"{self.creative_rejected} rejected, {self.creative_deferred} deferred, "
                    f"accepted rate {self.accepted_creative_rate:.2f}"
                ),
                "",
                "## Sources",
                *[f"- {source_id}" for source_id in self.source_ids],
            ]
        )


def build_strategy_scorecard(strategy_id: str, records: Iterable[Any]) -> StrategyScorecard:
    """Aggregate matching records into a strategy scorecard.

    Records may be dict-like or simple objects with attributes. Unknown outcomes or
    creative statuses are ignored in their category counts while still contributing
    to total/cost/latency when the strategy id matches.
    """

    normalized_strategy_id = _non_empty(strategy_id, "strategy_id")
    matching_records = [
        record for record in records if _optional_string(_record_value(record, "strategy_id")) == normalized_strategy_id
    ]

    source_ids = _collect_source_ids(matching_records)
    if not source_ids:
        source_ids = [f"scorecard:{normalized_strategy_id}"]

    passed = failed = blocked = unsafe = 0
    teacher_call_total = 0
    cost_total = 0.0
    latency_total = 0.0
    creative_accepted = creative_rejected = creative_deferred = 0

    for record in matching_records:
        outcome = _optional_string(_record_value(record, "outcome"))
        match outcome:
            case "passed":
                passed += 1
            case "failed":
                failed += 1
            case "blocked":
                blocked += 1
            case "unsafe":
                unsafe += 1

        teacher_call_total += _non_negative_int(_record_value(record, "teacher_call_count"), "teacher_call_count")
        cost_total += _non_negative_float(_record_value(record, "cost_units"), "cost_units")
        latency_total += _non_negative_float(_record_value(record, "latency_units"), "latency_units")

        creative_status = _optional_string(_record_value(record, "creative_acceptance_status"))
        match creative_status:
            case "accepted":
                creative_accepted += 1
            case "rejected":
                creative_rejected += 1
            case "deferred":
                creative_deferred += 1

    return StrategyScorecard(
        strategy_id=normalized_strategy_id,
        total=len(matching_records),
        passed=passed,
        failed=failed,
        blocked=blocked,
        unsafe=unsafe,
        teacher_call_total=teacher_call_total,
        cost_total=cost_total,
        latency_total=latency_total,
        creative_accepted=creative_accepted,
        creative_rejected=creative_rejected,
        creative_deferred=creative_deferred,
        source_ids=source_ids,
    )


def _record_value(record: Any, field_name: str) -> Any:
    if isinstance(record, dict):
        return record.get(field_name)
    return getattr(record, field_name, None)


def _collect_source_ids(records: Iterable[Any]) -> list[str]:
    source_ids: list[str] = []
    seen: set[str] = set()
    for record in records:
        for field_name in ("record_id", "source_ids"):
            value = _record_value(record, field_name)
            values = value if isinstance(value, list) else [value]
            for source_id in values:
                normalized = _optional_string(source_id)
                if normalized is not None and normalized not in seen:
                    source_ids.append(normalized)
                    seen.add(normalized)
    return source_ids


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


def _non_negative_int(value: Any, field_name: str) -> int:
    if value is None:
        return 0
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return integer


def _non_negative_float(value: Any, field_name: str) -> float:
    if value is None:
        return 0.0
    number = float(value)
    if number < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return number
