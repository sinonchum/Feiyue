from __future__ import annotations

from feiyue_core.capability import (
    CapabilityLevel,
    TaskComplexity,
    WorkerPerformanceRecord,
    WorkerTaskResult,
    compare_levels,
    default_capability_ladder,
    rank_for,
)
from feiyue_core.curation import ProposalPatch, ReviewDecisionStatus, ReviewGate, build_distillation_proposal


def test_capability_evidence_connects_review_decision_to_worker_performance_record() -> None:
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

    record = WorkerPerformanceRecord(
        record_id="worker-performance-m7-demo-task",
        worker_id="worker-deepseek-v4-pro",
        model_id="deepseek-v4-pro",
        task_id=complexity.task_id,
        capability_level=complexity.required_level.value,
        result=WorkerTaskResult.PASSED,
        verifier_result="python -m pytest tests/test_curation_integration.py -q passed",
        teacher_call_count=1,
        repeated_mistake_category=None,
        curation_evidence_ids=[proposal.proposal_id, proposal.source_input_id],
        review_decision_ids=[review_decision.decision_id],
        source_ids=[complexity.task_id, review_decision.decision_id],
    )
    rendered_record = record.render_markdown()

    assert record.is_successful_without_teacher is False
    assert record.capability_level == CapabilityLevel.BOUNDED_DEBUG.value
    assert "# Worker Performance Record: worker-performance-m7-demo-task" in rendered_record
    assert "- Capability Level: bounded_debug" in rendered_record
    assert "- Teacher Calls: 1" in rendered_record
    assert "review-m7-demo-task" in rendered_record
