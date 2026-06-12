from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.capability import (
    CapabilityRecommendation,
    CapabilityRecommendationAction,
    CapabilityRuleThresholds,
    WorkerPerformanceRecord,
    WorkerTaskResult,
    evaluate_records_for_capability,
)


def make_record(
    record_id: str,
    *,
    model_id: str = "model-a",
    capability_level: str = "single_file_change",
    result: WorkerTaskResult = WorkerTaskResult.PASSED,
    teacher_call_count: int = 0,
    repeated_mistake_category: str | None = None,
    curation_evidence_ids: list[str] | None = None,
    review_decision_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
) -> WorkerPerformanceRecord:
    return WorkerPerformanceRecord(
        record_id=record_id,
        worker_id="worker-a",
        model_id=model_id,
        task_id=f"task-{record_id}",
        capability_level=capability_level,
        result=result,
        verifier_result="pytest",
        teacher_call_count=teacher_call_count,
        repeated_mistake_category=repeated_mistake_category,
        curation_evidence_ids=curation_evidence_ids or [f"evidence-{record_id}"],
        review_decision_ids=review_decision_ids or [],
        source_ids=source_ids or [f"source-{record_id}"],
    )


def test_recommendation_validates_non_empty_source_ids() -> None:
    with pytest.raises(ValidationError):
        CapabilityRecommendation(
            recommendation_id="rec-1",
            model_id="model-a",
            capability_level="single_file_change",
            action=CapabilityRecommendationAction.KEEP,
            rationale="No evidence yet.",
            source_ids=[],
        )

    with pytest.raises(ValidationError):
        CapabilityRecommendation(
            recommendation_id="rec-1",
            model_id="model-a",
            capability_level="single_file_change",
            action="keep",
            rationale="No evidence yet.",
            source_ids=["source-1", ""],
        )


def test_single_success_keeps_and_renders_deterministic_markdown() -> None:
    recommendation = evaluate_records_for_capability(
        "model-a",
        "single_file_change",
        [make_record("record-1")],
    )

    assert recommendation.action is CapabilityRecommendationAction.KEEP
    assert recommendation.source_ids == ["record-1", "evidence-record-1", "source-record-1"]
    assert recommendation.render_markdown() == "\n".join(
        [
            "# Capability Recommendation: rec-model-a-single_file_change-keep",
            "",
            "- Model: model-a",
            "- Capability Level: single_file_change",
            "- Action: keep",
            "",
            "## Rationale",
            "1 matching record(s): 1 passed, teacher call rate 0.00, no repeated mistake category reached 2.",
            "",
            "## Sources",
            "- record-1",
            "- evidence-record-1",
            "- source-record-1",
        ]
    )


def test_promotes_after_enough_successes_without_teacher_calls() -> None:
    recommendation = evaluate_records_for_capability(
        "model-a",
        "single_file_change",
        [make_record("record-1"), make_record("record-2"), make_record("record-3")],
    )

    assert recommendation.action is CapabilityRecommendationAction.PROMOTE
    assert "3 passed" in recommendation.rationale


def test_keeps_when_teacher_call_rate_exceeds_promotion_threshold() -> None:
    recommendation = evaluate_records_for_capability(
        "model-a",
        "single_file_change",
        [
            make_record("record-1"),
            make_record("record-2"),
            make_record("record-3", teacher_call_count=1),
        ],
    )

    assert recommendation.action is CapabilityRecommendationAction.KEEP
    assert "teacher call rate 0.33" in recommendation.rationale


def test_promotes_when_custom_teacher_call_rate_threshold_allows_it() -> None:
    recommendation = evaluate_records_for_capability(
        "model-a",
        "single_file_change",
        [
            make_record("record-1"),
            make_record("record-2"),
            make_record("record-3", teacher_call_count=1),
        ],
        thresholds=CapabilityRuleThresholds(max_teacher_call_rate_for_promotion=0.34),
    )

    assert recommendation.action is CapabilityRecommendationAction.PROMOTE


def test_repeated_mistakes_demote_before_promotion() -> None:
    recommendation = evaluate_records_for_capability(
        "model-a",
        "single_file_change",
        [
            make_record("record-1", repeated_mistake_category="formatting"),
            make_record("record-2", repeated_mistake_category="formatting"),
            make_record("record-3"),
        ],
    )

    assert recommendation.action is CapabilityRecommendationAction.DEMOTE
    assert "formatting repeated 2 time(s)" in recommendation.rationale


def test_unsafe_escalates_to_teacher_before_demotion() -> None:
    recommendation = evaluate_records_for_capability(
        "model-a",
        "single_file_change",
        [
            make_record("record-1", result=WorkerTaskResult.UNSAFE, repeated_mistake_category="security"),
            make_record("record-2", result=WorkerTaskResult.FAILED, repeated_mistake_category="security"),
        ],
    )

    assert recommendation.action is CapabilityRecommendationAction.ESCALATE_TO_TEACHER
    assert "unsafe" in recommendation.rationale


def test_evaluation_filters_to_matching_model_and_capability_and_dedupes_sources() -> None:
    recommendation = evaluate_records_for_capability(
        "model-a",
        "single_file_change",
        [
            make_record(
                "record-1",
                curation_evidence_ids=["shared", "evidence-1"],
                review_decision_ids=["review-1", "shared"],
                source_ids=["source-1", "record-1"],
            ),
            make_record("record-2", model_id="model-b"),
            make_record("record-3", capability_level="bounded_debug"),
        ],
    )

    assert recommendation.action is CapabilityRecommendationAction.KEEP
    assert recommendation.source_ids == ["record-1", "shared", "evidence-1", "review-1", "source-1"]
