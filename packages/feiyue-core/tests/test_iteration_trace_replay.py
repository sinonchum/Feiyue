from __future__ import annotations

from feiyue_core.audit import JsonlTraceWriter
from feiyue_core.generation import IterationResumeContextBuilder, IterationTraceReader
from feiyue_core.schemas import TraceEvent, TraceEventType


def append_event(writer: JsonlTraceWriter, event_id: str, event_type: TraceEventType, data: dict) -> None:
    writer.append(
        TraceEvent(
            id=event_id,
            session_id="sess_replay_001",
            type=event_type,
            message=event_type.value.replace("_", " "),
            data=data,
        )
    )


def write_successful_trace(trace_path) -> None:
    writer = JsonlTraceWriter(trace_path)
    append_event(
        writer,
        "evt_001",
        TraceEventType.CANDIDATE_GENERATED,
        {
            "task_id": "task_replay_001",
            "candidate_id": "cand_initial",
            "prompt_template_hash": "sha256:templatehash",
            "prompt_rendered_hash": "sha256:renderedhash1",
            "provider_request_id": "fake-student-req-001",
            "routing_trigger": "none",
        },
    )
    append_event(
        writer,
        "evt_002",
        TraceEventType.VERIFICATION_FAILED,
        {
            "candidate_id": "cand_initial",
            "verification_result_id": "verify_fail_001",
            "verifier_name": "pytest",
            "failure_category": "pytest_failure",
            "confidence": 0.9,
        },
    )
    append_event(
        writer,
        "evt_003",
        TraceEventType.FEEDBACK_ANALYZED,
        {
            "task_id": "task_replay_001",
            "candidate_id": "cand_initial",
            "verification_result_id": "verify_fail_001",
            "passed": False,
            "feedback_category": "pytest_failure",
            "action_items": ["Inspect failing assertion output", "Rerun pytest after candidate revision"],
        },
    )
    append_event(
        writer,
        "evt_004",
        TraceEventType.TEACHER_GUIDANCE_REQUESTED,
        {
            "task_id": "task_replay_001",
            "candidate_id": "cand_initial",
            "provider_request_id": "fake-teacher-req-001",
            "teacher_trigger": "consecutive_student_failures",
            "teacher_model": "fake-teacher-001",
        },
    )
    append_event(
        writer,
        "evt_005",
        TraceEventType.CANDIDATE_REVISED,
        {
            "task_id": "task_replay_001",
            "candidate_id": "cand_revised",
            "parent_candidate_id": "cand_initial",
            "revision_index": 1,
            "feedback_category": "pytest_failure",
        },
    )
    append_event(
        writer,
        "evt_006",
        TraceEventType.VERIFICATION_PASSED,
        {
            "candidate_id": "cand_revised",
            "verification_result_id": "verify_pass_001",
            "verifier_name": "pytest",
            "failure_category": None,
            "confidence": 0.95,
        },
    )
    append_event(
        writer,
        "evt_007",
        TraceEventType.FEEDBACK_ANALYZED,
        {
            "task_id": "task_replay_001",
            "candidate_id": "cand_revised",
            "verification_result_id": "verify_pass_001",
            "passed": True,
            "feedback_category": "passed",
            "action_items": ["Promote candidate or run next acceptance gate"],
        },
    )
    append_event(
        writer,
        "evt_008",
        TraceEventType.ITERATION_COMPLETED,
        {
            "task_id": "task_replay_001",
            "passed": True,
            "final_candidate_id": "cand_revised",
            "final_candidate_status": "verified",
            "candidate_count": 2,
            "verification_count": 2,
            "teacher_guidance_count": 1,
        },
    )


def test_iteration_trace_reader_replays_jsonl_events_and_ignores_blank_lines(tmp_path) -> None:
    trace_path = tmp_path / "iteration.jsonl"
    write_successful_trace(trace_path)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write("\n")

    events = IterationTraceReader(trace_path).read_events()

    assert len(events) == 8
    assert events[0].type == TraceEventType.CANDIDATE_GENERATED
    assert events[-1].type == TraceEventType.ITERATION_COMPLETED
    assert all(event.session_id == "sess_replay_001" for event in events)


def test_resume_context_builder_reconstructs_completed_iteration_context(tmp_path) -> None:
    trace_path = tmp_path / "iteration.jsonl"
    write_successful_trace(trace_path)

    context = IterationResumeContextBuilder().build(IterationTraceReader(trace_path).read_events())

    assert context.session_id == "sess_replay_001"
    assert context.task_id == "task_replay_001"
    assert context.latest_candidate_id == "cand_revised"
    assert context.parent_candidate_id == "cand_initial"
    assert context.latest_verification_result_id == "verify_pass_001"
    assert context.latest_feedback_category == "passed"
    assert context.teacher_guidance_already_requested is True
    assert context.completed is True
    assert context.passed is True
    assert context.next_safe_action == "promote verified candidate or run next acceptance gate"
    assert "cand_initial -> cand_revised" in context.resume_summary
    assert "do not request duplicate teacher guidance" in context.resume_summary


def test_resume_context_builder_marks_unresolved_failure_without_repeating_teacher(tmp_path) -> None:
    trace_path = tmp_path / "iteration-incomplete.jsonl"
    writer = JsonlTraceWriter(trace_path)
    append_event(
        writer,
        "evt_001",
        TraceEventType.CANDIDATE_GENERATED,
        {
            "task_id": "task_replay_002",
            "candidate_id": "cand_initial",
            "prompt_rendered_hash": "sha256:renderedhash1",
            "provider_request_id": "fake-student-req-001",
            "routing_trigger": "none",
        },
    )
    append_event(
        writer,
        "evt_002",
        TraceEventType.VERIFICATION_FAILED,
        {
            "candidate_id": "cand_initial",
            "verification_result_id": "verify_fail_002",
            "verifier_name": "pytest",
            "failure_category": "pytest_failure",
            "confidence": 0.9,
        },
    )
    append_event(
        writer,
        "evt_003",
        TraceEventType.FEEDBACK_ANALYZED,
        {
            "task_id": "task_replay_002",
            "candidate_id": "cand_initial",
            "verification_result_id": "verify_fail_002",
            "passed": False,
            "feedback_category": "pytest_failure",
            "action_items": ["Inspect failing assertion output"],
        },
    )
    append_event(
        writer,
        "evt_004",
        TraceEventType.TEACHER_GUIDANCE_REQUESTED,
        {
            "task_id": "task_replay_002",
            "candidate_id": "cand_initial",
            "provider_request_id": "fake-teacher-req-002",
            "teacher_trigger": "consecutive_student_failures",
            "teacher_model": "fake-teacher-001",
        },
    )

    context = IterationResumeContextBuilder().build(IterationTraceReader(trace_path).read_events())

    assert context.completed is False
    assert context.passed is False
    assert context.latest_candidate_id == "cand_initial"
    assert context.latest_verification_result_id == "verify_fail_002"
    assert context.latest_feedback_category == "pytest_failure"
    assert context.teacher_guidance_already_requested is True
    assert context.next_safe_action == "revise latest candidate using existing teacher guidance; do not request duplicate teacher guidance"
    assert "unresolved failure pytest_failure" in context.resume_summary
