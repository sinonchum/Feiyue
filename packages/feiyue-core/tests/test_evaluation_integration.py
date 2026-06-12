from __future__ import annotations

from feiyue_core.capability import CapabilityLevel
from feiyue_core.creative import UserSelectionFeedback, UserSelectionStatus
from feiyue_core.evaluation import (
    CreativeAcceptanceStatus,
    StrategyEvaluationRecord,
    StrategyOutcome,
    build_strategy_scorecard,
)


def test_strategy_evaluation_records_aggregate_into_scorecard() -> None:
    feedback = UserSelectionFeedback(
        feedback_id="selection-eval-demo",
        brief_id="creative-brief-eval-demo",
        selected_variant_id="variant-eval-demo",
        status=UserSelectionStatus.ACCEPTED,
        rationale="Accepted because it had low implementation risk and clear verification.",
        useful_aspects=["clear verification", "low implementation risk"],
        source_ids=["creative-brief-eval-demo", "variant-eval-demo"],
    )
    records = [
        StrategyEvaluationRecord(
            record_id="eval-record-1",
            strategy_id="weak-plus-feiyue",
            model_id="deepseek-v4-pro",
            task_id="task-1",
            capability_level=CapabilityLevel.BOUNDED_DEBUG.value,
            outcome=StrategyOutcome.PASSED,
            teacher_call_count=0,
            cost_units=1.0,
            latency_units=2.0,
            creative_acceptance_status=CreativeAcceptanceStatus.ACCEPTED,
            source_ids=[feedback.feedback_id, "worker-performance-1"],
        ),
        StrategyEvaluationRecord(
            record_id="eval-record-2",
            strategy_id="weak-plus-feiyue",
            model_id="deepseek-v4-pro",
            task_id="task-2",
            capability_level=CapabilityLevel.BOUNDED_DEBUG.value,
            outcome=StrategyOutcome.PASSED,
            teacher_call_count=1,
            cost_units=2.0,
            latency_units=4.0,
            creative_acceptance_status=CreativeAcceptanceStatus.DEFERRED,
            source_ids=["review-decision-2", "worker-performance-2"],
        ),
        StrategyEvaluationRecord(
            record_id="eval-record-3",
            strategy_id="weak-plus-feiyue",
            model_id="deepseek-v4-pro",
            task_id="task-3",
            capability_level=CapabilityLevel.MODULE_FEATURE_SLICE.value,
            outcome=StrategyOutcome.UNSAFE,
            teacher_call_count=1,
            cost_units=3.0,
            latency_units=6.0,
            creative_acceptance_status=CreativeAcceptanceStatus.REJECTED,
            source_ids=["safety-gate-3"],
        ),
        StrategyEvaluationRecord(
            record_id="eval-record-other",
            strategy_id="weak-only",
            model_id="deepseek-v4-pro",
            task_id="task-other",
            capability_level=CapabilityLevel.BOUNDED_DEBUG.value,
            outcome=StrategyOutcome.FAILED,
            source_ids=["other-strategy"],
        ),
    ]

    scorecard = build_strategy_scorecard("weak-plus-feiyue", records)
    rendered = scorecard.render_markdown()

    assert scorecard.total == 3
    assert scorecard.passed == 2
    assert scorecard.unsafe == 1
    assert scorecard.pass_rate == 2 / 3
    assert scorecard.teacher_call_rate == 2 / 3
    assert scorecard.average_cost == 2.0
    assert scorecard.average_latency == 4.0
    assert scorecard.accepted_creative_rate == 1 / 3
    assert scorecard.source_ids[:3] == ["eval-record-1", feedback.feedback_id, "worker-performance-1"]
    assert "# Strategy Scorecard: weak-plus-feiyue" in rendered
    assert "- Outcomes: 2 passed, 0 failed, 0 blocked, 1 unsafe" in rendered
    assert "accepted rate 0.33" in rendered


def test_zero_record_strategy_scorecard_has_zero_rates() -> None:
    scorecard = build_strategy_scorecard("empty-strategy", [])

    assert scorecard.total == 0
    assert scorecard.pass_rate == 0.0
    assert scorecard.teacher_call_rate == 0.0
    assert scorecard.average_cost == 0.0
    assert scorecard.accepted_creative_rate == 0.0
    assert scorecard.source_ids == ["scorecard:empty-strategy"]
