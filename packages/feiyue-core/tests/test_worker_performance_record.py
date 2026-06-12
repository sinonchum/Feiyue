import pytest
from pydantic import ValidationError

from feiyue_core.capability.performance_record import (
    WorkerPerformanceRecord,
    WorkerTaskResult,
)


def _record(**overrides: object) -> WorkerPerformanceRecord:
    data = {
        "record_id": "wpr-001",
        "worker_id": "worker-1",
        "model_id": "claude-sonnet",
        "task_id": "task-123",
        "capability_level": "level-2",
        "result": WorkerTaskResult.PASSED,
        "verifier_result": "pytest passed",
        "curation_evidence_ids": ["evidence-1", "evidence-2"],
        "source_ids": ["trace-1"],
    }
    data.update(overrides)
    return WorkerPerformanceRecord(**data)


def test_worker_task_result_literals_are_stable() -> None:
    assert WorkerTaskResult.PASSED.value == "passed"
    assert WorkerTaskResult.FAILED.value == "failed"
    assert WorkerTaskResult.BLOCKED.value == "blocked"
    assert WorkerTaskResult.UNSAFE.value == "unsafe"


def test_worker_performance_record_accepts_required_fields_and_defaults() -> None:
    record = _record(result="passed")

    assert record.record_id == "wpr-001"
    assert record.result is WorkerTaskResult.PASSED
    assert record.teacher_call_count == 0
    assert record.repeated_mistake_category is None
    assert record.review_decision_ids == []
    assert record.is_successful_without_teacher is True


def test_is_successful_without_teacher_requires_passed_result_and_no_teacher_calls() -> None:
    assert _record(result=WorkerTaskResult.PASSED, teacher_call_count=0).is_successful_without_teacher is True
    assert _record(result=WorkerTaskResult.PASSED, teacher_call_count=1).is_successful_without_teacher is False
    assert _record(result=WorkerTaskResult.FAILED, teacher_call_count=0).is_successful_without_teacher is False


@pytest.mark.parametrize(
    "field_name",
    ["worker_id", "model_id", "task_id", "capability_level", "verifier_result"],
)
def test_required_string_fields_reject_blank_values(field_name: str) -> None:
    with pytest.raises(ValidationError, match=field_name):
        _record(**{field_name: "  \t"})


def test_teacher_call_count_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="teacher_call_count"):
        _record(teacher_call_count=-1)


@pytest.mark.parametrize("field_name", ["curation_evidence_ids", "source_ids"])
def test_required_id_lists_must_be_non_empty(field_name: str) -> None:
    with pytest.raises(ValidationError, match=field_name):
        _record(**{field_name: []})


@pytest.mark.parametrize(
    "field_name",
    ["curation_evidence_ids", "review_decision_ids", "source_ids"],
)
def test_id_lists_reject_empty_ids(field_name: str) -> None:
    with pytest.raises(ValidationError, match=field_name):
        _record(**{field_name: ["valid-id", "  "]})


def test_render_markdown_is_deterministic() -> None:
    record = _record(
        result=WorkerTaskResult.BLOCKED,
        teacher_call_count=2,
        repeated_mistake_category="missed-edge-case",
        review_decision_ids=["review-1", "review-2"],
    )

    assert record.render_markdown() == (
        "# Worker Performance Record: wpr-001\n"
        "\n"
        "- Worker: worker-1\n"
        "- Model: claude-sonnet\n"
        "- Task: task-123\n"
        "- Capability Level: level-2\n"
        "- Result: blocked\n"
        "- Verifier Result: pytest passed\n"
        "- Teacher Calls: 2\n"
        "- Repeated Mistake Category: missed-edge-case\n"
        "- Curation Evidence IDs: evidence-1, evidence-2\n"
        "- Review Decision IDs: review-1, review-2\n"
        "- Source IDs: trace-1\n"
    )


def test_render_markdown_uses_none_and_empty_list_markers() -> None:
    record = _record()

    assert "- Repeated Mistake Category: None\n" in record.render_markdown()
    assert "- Review Decision IDs: None\n" in record.render_markdown()
