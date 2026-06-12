from __future__ import annotations

from dataclasses import dataclass

from feiyue_core.evaluation import StrategyScorecard, build_strategy_scorecard


@dataclass(frozen=True)
class StrategyRecord:
    record_id: str
    strategy_id: str
    outcome: str
    teacher_call_count: int = 0
    cost_units: float = 0.0
    latency_units: float = 0.0
    creative_acceptance_status: str | None = None
    source_ids: list[str] | None = None


def test_build_strategy_scorecard_aggregates_matching_dicts_and_objects() -> None:
    records = [
        {
            "record_id": "record-1",
            "strategy_id": "strategy-a",
            "outcome": "passed",
            "teacher_call_count": 2,
            "cost_units": 4.5,
            "latency_units": 10.0,
            "creative_acceptance_status": "accepted",
            "source_ids": ["dataset-1"],
        },
        StrategyRecord(
            record_id="record-2",
            strategy_id="strategy-a",
            outcome="failed",
            teacher_call_count=0,
            cost_units=1.5,
            latency_units=20.0,
            creative_acceptance_status="rejected",
            source_ids=["dataset-1", "review-2"],
        ),
        StrategyRecord(
            record_id="record-3",
            strategy_id="strategy-a",
            outcome="blocked",
            teacher_call_count=1,
            cost_units=2.0,
            latency_units=30.0,
            creative_acceptance_status="deferred",
        ),
        {
            "record_id": "record-4",
            "strategy_id": "strategy-a",
            "outcome": "unsafe",
            "teacher_call_count": 0,
            "cost_units": 0.5,
            "latency_units": 40.0,
            "creative_acceptance_status": None,
            "source_ids": ["safety-4"],
        },
        {
            "record_id": "other-1",
            "strategy_id": "strategy-b",
            "outcome": "passed",
            "teacher_call_count": 9,
            "cost_units": 99.0,
            "latency_units": 99.0,
            "creative_acceptance_status": "accepted",
            "source_ids": ["other-source"],
        },
    ]

    scorecard = build_strategy_scorecard("strategy-a", records)

    assert scorecard == StrategyScorecard(
        strategy_id="strategy-a",
        total=4,
        passed=1,
        failed=1,
        blocked=1,
        unsafe=1,
        teacher_call_total=3,
        cost_total=8.5,
        latency_total=100.0,
        creative_accepted=1,
        creative_rejected=1,
        creative_deferred=1,
        source_ids=["record-1", "dataset-1", "record-2", "review-2", "record-3", "record-4", "safety-4"],
    )
    assert scorecard.pass_rate == 0.25
    assert scorecard.teacher_call_rate == 0.75
    assert scorecard.average_cost == 2.125
    assert scorecard.average_latency == 25.0
    assert scorecard.accepted_creative_rate == 1 / 3


def test_zero_record_scorecard_has_zero_rates_and_fallback_source() -> None:
    scorecard = build_strategy_scorecard("strategy-empty", [])

    assert scorecard.total == 0
    assert scorecard.pass_rate == 0.0
    assert scorecard.teacher_call_rate == 0.0
    assert scorecard.average_cost == 0.0
    assert scorecard.average_latency == 0.0
    assert scorecard.accepted_creative_rate == 0.0
    assert scorecard.source_ids == ["scorecard:strategy-empty"]


def test_strategy_scorecard_renders_deterministic_markdown() -> None:
    scorecard = StrategyScorecard(
        strategy_id="strategy-a",
        total=2,
        passed=1,
        failed=1,
        blocked=0,
        unsafe=0,
        teacher_call_total=1,
        cost_total=3.0,
        latency_total=12.0,
        creative_accepted=1,
        creative_rejected=1,
        creative_deferred=0,
        source_ids=["record-1", "dataset-1"],
    )

    assert scorecard.render_markdown() == "\n".join(
        [
            "# Strategy Scorecard: strategy-a",
            "",
            "- Total Records: 2",
            "- Outcomes: 1 passed, 1 failed, 0 blocked, 0 unsafe",
            "- Pass Rate: 0.50",
            "- Teacher Calls: 1 total, rate 0.50",
            "- Cost: 3.00 total, average 1.50",
            "- Latency: 12.00 total, average 6.00",
            "- Creative Decisions: 1 accepted, 1 rejected, 0 deferred, accepted rate 0.50",
            "",
            "## Sources",
            "- record-1",
            "- dataset-1",
        ]
    )
