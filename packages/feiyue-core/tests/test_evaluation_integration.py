from __future__ import annotations

from feiyue_core.capability import CapabilityLevel
from feiyue_core.creative import UserSelectionFeedback, UserSelectionStatus
from feiyue_core.evaluation import (
    BenchmarkTask,
    BenchmarkSuite,
    CreativeAcceptanceStatus,
    StrategyEvaluationRecord,
    StrategyOutcome,
    build_strategy_comparison_report,
    build_strategy_scorecard,
    cost_normalized_quality,
    default_toy_benchmark_suite,
)


def test_strategy_evaluation_records_scorecards_and_comparison_report() -> None:
    suite = default_toy_benchmark_suite()
    assert len(suite.tasks) == 3
    assert "# Benchmark Suite: toy-benchmark-suite" in suite.render_markdown()

    custom_suite = BenchmarkSuite(
        suite_id="custom-eval-suite",
        tasks=[
            BenchmarkTask(
                task_id="eval.creative_acceptance",
                required_capability_level=CapabilityLevel.IMPLEMENTATION_OPTIONS.value,
                expected_verifier="pytest:tests/test_creative_integration.py",
                category="creative",
                source_ids=["m9-integration"],
            )
        ],
    )
    assert custom_suite.tasks[0].task_id == "eval.creative_acceptance"

    feedback = UserSelectionFeedback(
        feedback_id="selection-eval-demo",
        brief_id="creative-brief-eval-demo",
        selected_variant_id="variant-eval-demo",
        status=UserSelectionStatus.ACCEPTED,
        rationale="Accepted because it had low implementation risk and clear verification.",
        useful_aspects=["clear verification", "low implementation risk"],
        source_ids=["creative-brief-eval-demo", "variant-eval-demo"],
    )
    feiyue_records = [
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
    ]
    weak_only_records = [
        StrategyEvaluationRecord(
            record_id="weak-only-1",
            strategy_id="weak-only",
            model_id="deepseek-v4-pro",
            task_id="task-1",
            capability_level=CapabilityLevel.BOUNDED_DEBUG.value,
            outcome=StrategyOutcome.FAILED,
            teacher_call_count=0,
            cost_units=0.5,
            latency_units=1.0,
            creative_acceptance_status=CreativeAcceptanceStatus.REJECTED,
            source_ids=["weak-only-evidence"],
        )
    ]

    feiyue_scorecard = build_strategy_scorecard("weak-plus-feiyue", feiyue_records + weak_only_records)
    weak_only_scorecard = build_strategy_scorecard("weak-only", feiyue_records + weak_only_records)
    comparison = build_strategy_comparison_report(
        "strategy-comparison-eval-demo",
        [feiyue_scorecard, weak_only_scorecard],
    )
    rendered = comparison.render_markdown()

    assert feiyue_scorecard.total == 3
    assert feiyue_scorecard.pass_rate == 2 / 3
    assert feiyue_scorecard.unsafe == 1
    assert feiyue_scorecard.accepted_creative_rate == 1 / 3
    assert weak_only_scorecard.pass_rate == 0.0
    assert comparison.best_pass_rate_strategy == "weak-plus-feiyue"
    assert comparison.lowest_average_cost_strategy == "weak-only"
    assert comparison.unsafe_counts == {"weak-only": 0, "weak-plus-feiyue": 1}
    assert cost_normalized_quality(feiyue_scorecard) == feiyue_scorecard.pass_rate / feiyue_scorecard.average_cost
    assert "# Strategy Comparison Report: strategy-comparison-eval-demo" in rendered
    assert "unsafe 1" in rendered


def test_zero_record_strategy_scorecard_has_zero_rates() -> None:
    scorecard = build_strategy_scorecard("empty-strategy", [])

    assert scorecard.total == 0
    assert scorecard.pass_rate == 0.0
    assert scorecard.teacher_call_rate == 0.0
    assert scorecard.average_cost == 0.0
    assert scorecard.accepted_creative_rate == 0.0
    assert scorecard.source_ids == ["scorecard:empty-strategy"]
