from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.evaluation import (
    StrategyComparisonReport,
    StrategyScorecard,
    build_strategy_comparison_report,
    cost_normalized_quality,
)


def make_scorecard(
    strategy_id: str,
    *,
    total: int = 10,
    passed: int = 5,
    failed: int = 5,
    unsafe: int = 0,
    teacher_call_total: int = 0,
    cost_total: float = 10.0,
    source_ids: list[str] | None = None,
) -> StrategyScorecard:
    return StrategyScorecard(
        strategy_id=strategy_id,
        total=total,
        passed=passed,
        failed=failed,
        blocked=0,
        unsafe=unsafe,
        teacher_call_total=teacher_call_total,
        cost_total=cost_total,
        latency_total=0.0,
        creative_accepted=0,
        creative_rejected=0,
        creative_deferred=0,
        source_ids=source_ids or [f"source:{strategy_id}"],
    )


def test_build_strategy_comparison_report_selects_winners_with_tie_breakers() -> None:
    scorecards = [
        make_scorecard(
            "strategy-c",
            passed=8,
            unsafe=1,
            teacher_call_total=1,
            cost_total=12.0,
            source_ids=["dataset-2", "run-c"],
        ),
        make_scorecard(
            "strategy-a",
            passed=8,
            unsafe=2,
            teacher_call_total=4,
            cost_total=8.0,
            source_ids=["dataset-1", "run-a"],
        ),
        make_scorecard(
            "strategy-b",
            passed=7,
            unsafe=0,
            teacher_call_total=0,
            cost_total=8.0,
            source_ids=["dataset-1", "run-b"],
        ),
    ]

    report = build_strategy_comparison_report("comparison-1", scorecards)

    assert report == StrategyComparisonReport(
        report_id="comparison-1",
        scorecards=[scorecards[1], scorecards[2], scorecards[0]],
        best_pass_rate_strategy="strategy-a",
        lowest_average_cost_strategy="strategy-a",
        lowest_teacher_call_rate_strategy="strategy-b",
        unsafe_counts={"strategy-a": 2, "strategy-b": 0, "strategy-c": 1},
        source_ids=["dataset-1", "run-a", "run-b", "dataset-2", "run-c"],
    )


def test_cost_normalized_quality_uses_average_cost_or_one() -> None:
    paid = make_scorecard("paid", passed=9, cost_total=30.0)
    free = make_scorecard("free", passed=7, cost_total=0.0)

    assert cost_normalized_quality(paid) == pytest.approx(0.3)
    assert cost_normalized_quality(free) == pytest.approx(0.7)


def test_empty_scorecards_are_invalid() -> None:
    with pytest.raises(ValueError, match="scorecards must contain at least one scorecard"):
        build_strategy_comparison_report("comparison-empty", [])

    with pytest.raises(ValidationError, match="scorecards must contain at least one scorecard"):
        StrategyComparisonReport(
            report_id="comparison-empty",
            scorecards=[],
            best_pass_rate_strategy="none",
            lowest_average_cost_strategy="none",
            lowest_teacher_call_rate_strategy="none",
            unsafe_counts={},
            source_ids=["source"],
        )


def test_strategy_comparison_report_renders_deterministic_markdown() -> None:
    report = build_strategy_comparison_report(
        "comparison-1",
        [
            make_scorecard("strategy-b", passed=4, unsafe=1, teacher_call_total=0, cost_total=0.0),
            make_scorecard("strategy-a", passed=8, unsafe=0, teacher_call_total=2, cost_total=10.0),
        ],
    )

    assert report.render_markdown() == "\n".join(
        [
            "# Strategy Comparison Report: comparison-1",
            "",
            "- Best Pass Rate Strategy: strategy-a",
            "- Lowest Average Cost Strategy: strategy-b",
            "- Lowest Teacher Call Rate Strategy: strategy-b",
            "",
            "## Strategy Summary",
            (
                "- strategy-a: pass rate 0.80, average cost 1.00, teacher call rate 0.20, "
                "unsafe 0, cost-normalized quality 0.80"
            ),
            (
                "- strategy-b: pass rate 0.40, average cost 0.00, teacher call rate 0.00, "
                "unsafe 1, cost-normalized quality 0.40"
            ),
            "",
            "## Unsafe Counts",
            "- strategy-a: 0",
            "- strategy-b: 1",
            "",
            "## Sources",
            "- source:strategy-a",
            "- source:strategy-b",
        ]
    )
