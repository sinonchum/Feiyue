import pytest
from pydantic import ValidationError

from feiyue_core.evaluation.record import (
    CreativeAcceptanceStatus,
    StrategyEvaluationRecord,
    StrategyOutcome,
)


def _record(**overrides: object) -> StrategyEvaluationRecord:
    data = {
        "record_id": "ser-001",
        "strategy_id": "strategy-1",
        "model_id": "claude-sonnet",
        "task_id": "task-123",
        "capability_level": "level-2",
        "outcome": StrategyOutcome.PASSED,
        "source_ids": ["trace-1", "trace-2"],
    }
    data.update(overrides)
    return StrategyEvaluationRecord(**data)


def test_strategy_outcome_literals_are_stable() -> None:
    assert StrategyOutcome.PASSED.value == "passed"
    assert StrategyOutcome.FAILED.value == "failed"
    assert StrategyOutcome.BLOCKED.value == "blocked"
    assert StrategyOutcome.UNSAFE.value == "unsafe"


def test_creative_acceptance_status_literals_are_stable() -> None:
    assert CreativeAcceptanceStatus.ACCEPTED.value == "accepted"
    assert CreativeAcceptanceStatus.REJECTED.value == "rejected"
    assert CreativeAcceptanceStatus.DEFERRED.value == "deferred"
    assert CreativeAcceptanceStatus.NOT_APPLICABLE.value == "not_applicable"


def test_strategy_evaluation_record_accepts_required_fields_and_defaults() -> None:
    record = _record(outcome="passed")

    assert record.record_id == "ser-001"
    assert record.outcome is StrategyOutcome.PASSED
    assert record.teacher_call_count == 0
    assert record.cost_units == 0.0
    assert record.latency_units == 0.0
    assert record.creative_acceptance_status is CreativeAcceptanceStatus.NOT_APPLICABLE
    assert record.source_ids == ["trace-1", "trace-2"]


@pytest.mark.parametrize(
    "field_name",
    ["record_id", "strategy_id", "model_id", "task_id", "capability_level"],
)
def test_required_string_fields_reject_blank_values(field_name: str) -> None:
    with pytest.raises(ValidationError, match=field_name):
        _record(**{field_name: "  \t"})


@pytest.mark.parametrize("field_name", ["teacher_call_count", "cost_units", "latency_units"])
def test_numeric_fields_must_be_non_negative(field_name: str) -> None:
    with pytest.raises(ValidationError, match=field_name):
        _record(**{field_name: -1})


def test_source_ids_must_be_non_empty() -> None:
    with pytest.raises(ValidationError, match="source_ids"):
        _record(source_ids=[])


def test_source_ids_reject_empty_ids() -> None:
    with pytest.raises(ValidationError, match="source_ids"):
        _record(source_ids=["valid-id", "  "])


def test_render_markdown_is_deterministic() -> None:
    record = _record(
        outcome=StrategyOutcome.BLOCKED,
        teacher_call_count=2,
        cost_units=3.5,
        latency_units=42.25,
        creative_acceptance_status=CreativeAcceptanceStatus.DEFERRED,
    )

    assert record.render_markdown() == (
        "# Strategy Evaluation Record: ser-001\n"
        "\n"
        "- Strategy: strategy-1\n"
        "- Model: claude-sonnet\n"
        "- Task: task-123\n"
        "- Capability Level: level-2\n"
        "- Outcome: blocked\n"
        "- Teacher Calls: 2\n"
        "- Cost Units: 3.5\n"
        "- Latency Units: 42.25\n"
        "- Creative Acceptance Status: deferred\n"
        "- Source IDs: trace-1, trace-2\n"
    )
