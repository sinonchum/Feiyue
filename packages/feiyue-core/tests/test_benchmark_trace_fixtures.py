from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.evaluation import (
    BenchmarkTraceFixture,
    BenchmarkTraceRecord,
    default_strategy_trace_fixtures,
)


def test_default_strategy_trace_fixtures_are_deterministic_and_cover_required_strategies() -> None:
    first = default_strategy_trace_fixtures()
    second = default_strategy_trace_fixtures()

    assert first == second
    assert [fixture.strategy_id for fixture in first] == [
        "weak-only",
        "weak+task-contract",
        "weak+verifier",
        "weak+sparse-teacher",
        "strong-reference",
    ]
    assert all(fixture.records for fixture in first)
    assert all(record.provider_call_count == 0 for fixture in first for record in fixture.records)


def test_trace_fixture_round_trips_json_without_model_calls() -> None:
    fixture = BenchmarkTraceFixture(
        strategy_id="weak+verifier",
        records=[
            BenchmarkTraceRecord(
                record_id="trace-1",
                task_id="task.alpha",
                outcome="passed",
                teacher_call_count=0,
                weak_autonomous=True,
                repeated_mistake_count=0,
                cost_units=1.0,
                source_ids=["fixture:trace-1"],
            )
        ],
    )

    restored = BenchmarkTraceFixture.model_validate_json(fixture.model_dump_json())

    assert restored == fixture
    assert restored.records[0].provider_call_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"strategy_id": " "},
        {"records": []},
    ],
)
def test_trace_fixture_validates_required_fields(kwargs: dict[str, object]) -> None:
    data = {
        "strategy_id": "weak-only",
        "records": [
            BenchmarkTraceRecord(
                record_id="trace-1",
                task_id="task.alpha",
                outcome="failed",
                teacher_call_count=0,
                weak_autonomous=True,
                repeated_mistake_count=1,
                cost_units=1.0,
                source_ids=["fixture:trace-1"],
            )
        ],
    }
    data.update(kwargs)

    with pytest.raises(ValidationError):
        BenchmarkTraceFixture(**data)


def test_trace_record_rejects_provider_calls_and_negative_counts() -> None:
    with pytest.raises(ValidationError, match="provider_call_count"):
        BenchmarkTraceRecord(
            record_id="trace-1",
            task_id="task.alpha",
            outcome="passed",
            teacher_call_count=0,
            weak_autonomous=True,
            repeated_mistake_count=0,
            cost_units=1.0,
            provider_call_count=1,
            source_ids=["fixture:trace-1"],
        )

    with pytest.raises(ValidationError):
        BenchmarkTraceRecord(
            record_id="trace-1",
            task_id="task.alpha",
            outcome="passed",
            teacher_call_count=-1,
            weak_autonomous=True,
            repeated_mistake_count=0,
            cost_units=1.0,
            source_ids=["fixture:trace-1"],
        )
