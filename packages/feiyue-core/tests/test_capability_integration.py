from __future__ import annotations

from feiyue_core.capability import (
    CapabilityLevel,
    CapabilityRecommendationAction,
    TaskComplexity,
    WorkerPerformanceRecord,
    WorkerTaskResult,
    build_model_capability_profile,
    compare_levels,
    default_capability_ladder,
    evaluate_records_for_capability,
    rank_for,
)
from feiyue_core.curation import ProposalPatch, ReviewDecisionStatus, ReviewGate, build_distillation_proposal


def test_capability_evidence_connects_profile_to_promotion_recommendation() -> None:
    ladder = default_capability_ladder()
    assert [definition.rank for definition in ladder.definitions] == list(range(len(ladder.definitions)))
    assert compare_levels(CapabilityLevel.SINGLE_FILE_CHANGE, CapabilityLevel.BOUNDED_DEBUG) < 0
    assert rank_for(CapabilityLevel.MODULE_FEATURE_SLICE) == 5

    complexity = TaskComplexity(
        task_id="m7-demo-task",
        required_level=CapabilityLevel.BOUNDED_DEBUG,
        rationale="The task requires reproducing a failing curation integration path and proving the fix.",
        source_ids=["task-contract-m7-demo", "curation-smoke-m7-demo"],
    )
    rendered_complexity = complexity.render_markdown()
    assert "# Task Complexity: m7-demo-task" in rendered_complexity
    assert "bounded_debug" in rendered_complexity

    proposal = build_distillation_proposal(
        proposal_id="proposal-m7-demo-task",
        source_task_id=complexity.task_id,
        source_input_id="curator-input-m7-demo-task",
        patches=[
            ProposalPatch(
                asset_type="lesson",
                target_path=".hermes/lessons/m7-demo-task.md",
                summary="Preserve bounded-debug evidence for worker capability tracking.",
                proposed_content="# Lesson\n\nBounded debug requires verifier-backed evidence.\n",
                source_ids=[complexity.task_id, "teacher-guidance-m7-demo"],
            )
        ],
    )
    review_decision = ReviewGate().accept(
        proposal,
        decision_id="review-m7-demo-task",
        reviewer_id="human-reviewer",
        rationale="The evidence is verifier-backed and safe to use for capability records.",
    )
    assert review_decision.decision is ReviewDecisionStatus.ACCEPTED

    records = [
        WorkerPerformanceRecord(
            record_id=f"worker-performance-m7-demo-task-{index}",
            worker_id="worker-deepseek-v4-pro",
            model_id="deepseek-v4-pro",
            task_id=f"{complexity.task_id}-{index}",
            capability_level=complexity.required_level.value,
            result=WorkerTaskResult.PASSED,
            verifier_result="pytest passed with reviewed curation evidence",
            teacher_call_count=0,
            repeated_mistake_category=None,
            curation_evidence_ids=[proposal.proposal_id, proposal.source_input_id],
            review_decision_ids=[review_decision.decision_id],
            source_ids=[complexity.task_id, review_decision.decision_id],
        )
        for index in range(3)
    ]
    profile = build_model_capability_profile("deepseek-v4-pro", records)
    stats = profile.stats_by_level[CapabilityLevel.BOUNDED_DEBUG.value]

    assert stats.total == 3
    assert stats.passed == 3
    assert stats.pass_rate == 1.0
    assert stats.teacher_call_rate == 0.0
    assert stats.evidence_ids[:3] == [
        "worker-performance-m7-demo-task-0",
        proposal.proposal_id,
        proposal.source_input_id,
    ]
    assert stats.review_decision_ids == [review_decision.decision_id]
    assert "# Model Capability Profile: deepseek-v4-pro" in profile.render_markdown()

    recommendation = evaluate_records_for_capability(
        "deepseek-v4-pro",
        CapabilityLevel.BOUNDED_DEBUG.value,
        records,
    )
    rendered_recommendation = recommendation.render_markdown()

    assert recommendation.action is CapabilityRecommendationAction.PROMOTE
    assert proposal.proposal_id in recommendation.source_ids
    assert review_decision.decision_id in recommendation.source_ids
    assert "# Capability Recommendation:" in rendered_recommendation
    assert "- Action: promote" in rendered_recommendation


def test_capability_rules_escalate_unsafe_records_before_profile_promotion() -> None:
    records = [
        WorkerPerformanceRecord(
            record_id="unsafe-record",
            worker_id="worker-deepseek-v4-pro",
            model_id="deepseek-v4-pro",
            task_id="unsafe-task",
            capability_level=CapabilityLevel.BOUNDED_DEBUG.value,
            result=WorkerTaskResult.UNSAFE,
            verifier_result="safety gate blocked side effect",
            teacher_call_count=0,
            repeated_mistake_category=None,
            curation_evidence_ids=["curation-evidence-unsafe"],
            review_decision_ids=["review-unsafe"],
            source_ids=["trace-unsafe"],
        )
    ]

    profile = build_model_capability_profile("deepseek-v4-pro", records)
    stats = profile.stats_by_level[CapabilityLevel.BOUNDED_DEBUG.value]
    recommendation = evaluate_records_for_capability(
        "deepseek-v4-pro",
        CapabilityLevel.BOUNDED_DEBUG.value,
        records,
    )

    assert stats.unsafe == 1
    assert recommendation.action is CapabilityRecommendationAction.ESCALATE_TO_TEACHER
    assert "unsafe-record" in recommendation.source_ids
