"""Deterministic provider-free trace fixtures for benchmark strategy comparison."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from feiyue_core.evaluation.record import StrategyOutcome
from feiyue_core.schemas.common import FeiyueModel


class BenchmarkTraceRecord(FeiyueModel):
    """One deterministic trace outcome, intentionally free of provider calls."""

    record_id: str
    task_id: str
    outcome: StrategyOutcome | str
    teacher_call_count: int = Field(default=0, ge=0)
    weak_autonomous: bool = True
    repeated_mistake_count: int = Field(default=0, ge=0)
    cost_units: float = Field(default=0.0, ge=0.0)
    provider_call_count: int = Field(default=0, ge=0)
    source_ids: list[str]

    @field_validator("record_id", "task_id", mode="before")
    @classmethod
    def _validate_required_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must be non-empty")
            return stripped
        return value

    @field_validator("source_ids")
    @classmethod
    def _validate_source_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("source_ids must be non-empty")
        normalized: list[str] = []
        for source_id in value:
            if not isinstance(source_id, str):
                raise TypeError("source_ids entries must be strings")
            stripped = source_id.strip()
            if not stripped:
                raise ValueError("source_ids entries must be non-empty")
            normalized.append(stripped)
        return normalized

    @model_validator(mode="after")
    def _validate_provider_free(self) -> "BenchmarkTraceRecord":
        if self.provider_call_count != 0:
            raise ValueError("provider_call_count must be 0 for provider-free fixtures")
        return self


class BenchmarkTraceFixture(FeiyueModel):
    """Provider-free records for one benchmark strategy."""

    strategy_id: str
    records: list[BenchmarkTraceRecord]

    @field_validator("strategy_id", mode="before")
    @classmethod
    def _validate_strategy_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("strategy_id must be non-empty")
            return stripped
        return value

    @field_validator("records")
    @classmethod
    def _validate_records(cls, value: list[BenchmarkTraceRecord]) -> list[BenchmarkTraceRecord]:
        if not value:
            raise ValueError("records must be non-empty")
        return value


def default_strategy_trace_fixtures() -> list[BenchmarkTraceFixture]:
    """Return deterministic fixtures for expected Wave 2 benchmark strategies.

    These records are synthetic contract fixtures only. They do not call providers
    and must not be interpreted as real model performance.
    """

    return [
        _fixture(
            "weak-only",
            [
                _record("weak-only", "task.alpha", "passed", mistakes=0, cost=1.0),
                _record("weak-only", "task.beta", "failed", mistakes=1, cost=1.0),
                _record("weak-only", "task.gamma", "failed", mistakes=2, cost=1.0),
            ],
        ),
        _fixture(
            "weak+task-contract",
            [
                _record("weak+task-contract", "task.alpha", "passed", mistakes=0, cost=1.1),
                _record("weak+task-contract", "task.beta", "passed", mistakes=0, cost=1.1),
                _record("weak+task-contract", "task.gamma", "failed", mistakes=1, cost=1.1),
            ],
        ),
        _fixture(
            "weak+verifier",
            [
                _record("weak+verifier", "task.alpha", "passed", mistakes=0, cost=1.2),
                _record("weak+verifier", "task.beta", "passed", mistakes=0, cost=1.2),
                _record("weak+verifier", "task.gamma", "passed", mistakes=0, cost=1.2),
            ],
        ),
        _fixture(
            "weak+sparse-teacher",
            [
                _record("weak+sparse-teacher", "task.alpha", "passed", mistakes=0, cost=1.3),
                _record("weak+sparse-teacher", "task.beta", "passed", mistakes=0, cost=1.3, teacher_calls=1, autonomous=False),
                _record("weak+sparse-teacher", "task.gamma", "passed", mistakes=0, cost=1.3),
            ],
        ),
        _fixture(
            "strong-reference",
            [
                _record("strong-reference", "task.alpha", "passed", mistakes=0, cost=3.0, autonomous=False),
                _record("strong-reference", "task.beta", "passed", mistakes=0, cost=3.0, autonomous=False),
                _record("strong-reference", "task.gamma", "passed", mistakes=0, cost=3.0, autonomous=False),
            ],
        ),
    ]


def _fixture(strategy_id: str, records: list[BenchmarkTraceRecord]) -> BenchmarkTraceFixture:
    return BenchmarkTraceFixture(strategy_id=strategy_id, records=records)


def _record(
    strategy_id: str,
    task_id: str,
    outcome: str,
    *,
    mistakes: int,
    cost: float,
    teacher_calls: int = 0,
    autonomous: bool = True,
) -> BenchmarkTraceRecord:
    return BenchmarkTraceRecord(
        record_id=f"{strategy_id}:{task_id}",
        task_id=task_id,
        outcome=outcome,
        teacher_call_count=teacher_calls,
        weak_autonomous=autonomous,
        repeated_mistake_count=mistakes,
        cost_units=cost,
        provider_call_count=0,
        source_ids=["fixture:m9-real-benchmark-prep", f"strategy:{strategy_id}", f"task:{task_id}"],
    )
