from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.evaluation import (
    BenchmarkStrategyMetrics,
    build_benchmark_strategy_comparison,
    default_strategy_trace_fixtures,
)


def test_build_benchmark_strategy_comparison_aggregates_provider_free_metrics() -> None:
    fixtures = default_strategy_trace_fixtures()

    comparison = build_benchmark_strategy_comparison("m9-contract", fixtures)

    assert comparison.comparison_id == "m9-contract"
    assert [metric.strategy_id for metric in comparison.metrics] == [
        "strong-reference",
        "weak+task-contract",
        "weak+sparse-teacher",
        "weak+verifier",
        "weak-only",
    ]
    weak_only = comparison.metric_for("weak-only")
    assert weak_only.strategy_id == "weak-only"
    assert weak_only.total == 3
    assert weak_only.pass_rate == pytest.approx(1 / 3)
    assert weak_only.teacher_call_rate == 0.0
    assert weak_only.weak_autonomy_rate == 1.0
    assert weak_only.repeated_mistake_count == 3
    assert weak_only.cost_normalized_quality == pytest.approx(1 / 3)
    assert weak_only.regression is True
    sparse_teacher = comparison.metric_for("weak+sparse-teacher")
    assert sparse_teacher.teacher_call_rate == pytest.approx(1 / 3)
    assert sparse_teacher.weak_autonomy_rate == pytest.approx(2 / 3)
    assert sparse_teacher.regression is False
    assert comparison.baseline_strategy_id == "strong-reference"


def test_benchmark_strategy_comparison_requires_two_or_more_strategies() -> None:
    fixtures = default_strategy_trace_fixtures()[:1]

    with pytest.raises(ValueError, match="at least two"):
        build_benchmark_strategy_comparison("too-small", fixtures)


def test_benchmark_strategy_comparison_round_trips_json() -> None:
    comparison = build_benchmark_strategy_comparison("m9-contract", default_strategy_trace_fixtures())

    restored = type(comparison).model_validate_json(comparison.model_dump_json())

    assert restored == comparison
    assert restored.metric_for("strong-reference").regression is False


def test_benchmark_strategy_comparison_rejects_unknown_metric_lookup() -> None:
    comparison = build_benchmark_strategy_comparison("m9-contract", default_strategy_trace_fixtures())

    with pytest.raises(KeyError, match="missing"):
        comparison.metric_for("missing")


def test_benchmark_strategy_metrics_validate_rates() -> None:
    with pytest.raises(ValidationError):
        BenchmarkStrategyMetrics(
            strategy_id="bad",
            total=1,
            pass_rate=1.2,
            teacher_call_rate=0.0,
            weak_autonomy_rate=1.0,
            repeated_mistake_count=0,
            cost_normalized_quality=1.0,
            regression=False,
        )
