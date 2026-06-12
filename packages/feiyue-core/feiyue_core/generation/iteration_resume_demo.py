from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from feiyue_core.audit import JsonlTraceWriter
from feiyue_core.schemas import TraceEvent, TraceEventType

from .trace_replay import IterationResumeContextBuilder, IterationResumePromptBuilder, IterationTraceReader


def _append_event(writer: JsonlTraceWriter, *, event_id: str, event_type: TraceEventType, data: dict[str, Any]) -> None:
    writer.append(
        TraceEvent(
            id=event_id,
            session_id="sess_iteration_resume_demo",
            type=event_type,
            message=event_type.value.replace("_", " "),
            data=data,
        )
    )


def _write_demo_trace(trace_path: Path) -> None:
    writer = JsonlTraceWriter(trace_path)
    _append_event(
        writer,
        event_id="evt_demo_001",
        event_type=TraceEventType.CANDIDATE_GENERATED,
        data={
            "task_id": "task_iteration_resume_demo",
            "candidate_id": "cand_demo_initial",
            "prompt_template_hash": "sha256:demo_template_hash",
            "prompt_rendered_hash": "sha256:demo_rendered_hash_initial",
            "provider_request_id": "fake-student-demo-001",
            "routing_trigger": "none",
        },
    )
    _append_event(
        writer,
        event_id="evt_demo_002",
        event_type=TraceEventType.VERIFICATION_FAILED,
        data={
            "candidate_id": "cand_demo_initial",
            "verification_result_id": "verify_demo_fail",
            "verifier_name": "pytest",
            "failure_category": "pytest_failure",
            "confidence": 0.91,
        },
    )
    _append_event(
        writer,
        event_id="evt_demo_003",
        event_type=TraceEventType.FEEDBACK_ANALYZED,
        data={
            "task_id": "task_iteration_resume_demo",
            "candidate_id": "cand_demo_initial",
            "verification_result_id": "verify_demo_fail",
            "passed": False,
            "feedback_category": "pytest_failure",
            "action_items": ["Inspect failing assertion output", "Rerun pytest after candidate revision"],
        },
    )
    _append_event(
        writer,
        event_id="evt_demo_004",
        event_type=TraceEventType.TEACHER_GUIDANCE_REQUESTED,
        data={
            "task_id": "task_iteration_resume_demo",
            "candidate_id": "cand_demo_initial",
            "provider_request_id": "fake-teacher-demo-001",
            "teacher_trigger": "consecutive_student_failures",
            "teacher_model": "fake-teacher-001",
        },
    )
    _append_event(
        writer,
        event_id="evt_demo_005",
        event_type=TraceEventType.CANDIDATE_REVISED,
        data={
            "task_id": "task_iteration_resume_demo",
            "candidate_id": "cand_demo_revised",
            "parent_candidate_id": "cand_demo_initial",
            "revision_index": 1,
            "feedback_category": "pytest_failure",
        },
    )
    _append_event(
        writer,
        event_id="evt_demo_006",
        event_type=TraceEventType.VERIFICATION_PASSED,
        data={
            "candidate_id": "cand_demo_revised",
            "verification_result_id": "verify_demo_pass",
            "verifier_name": "pytest",
            "failure_category": None,
            "confidence": 0.97,
        },
    )
    _append_event(
        writer,
        event_id="evt_demo_007",
        event_type=TraceEventType.FEEDBACK_ANALYZED,
        data={
            "task_id": "task_iteration_resume_demo",
            "candidate_id": "cand_demo_revised",
            "verification_result_id": "verify_demo_pass",
            "passed": True,
            "feedback_category": "passed",
            "action_items": ["Promote candidate or run next acceptance gate"],
        },
    )
    _append_event(
        writer,
        event_id="evt_demo_008",
        event_type=TraceEventType.ITERATION_COMPLETED,
        data={
            "task_id": "task_iteration_resume_demo",
            "passed": True,
            "final_candidate_id": "cand_demo_revised",
            "final_candidate_status": "verified",
            "candidate_count": 2,
            "verification_count": 2,
            "teacher_guidance_count": 1,
        },
    )


def run_demo(root: str | Path) -> dict[str, Any]:
    demo_dir = Path(root) / "iteration-resume-demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    trace_path = demo_dir / "iteration-trace.jsonl"
    if trace_path.exists():
        trace_path.unlink()

    _write_demo_trace(trace_path)
    events = IterationTraceReader(trace_path).read_events()
    context = IterationResumeContextBuilder().build(events)
    resume_prompt = IterationResumePromptBuilder().build(context)

    return {
        "trace_path": str(trace_path),
        "trace_path_exists": trace_path.exists(),
        "event_count": len(events),
        "context": context.model_dump(mode="json"),
        "resume_prompt": resume_prompt,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a provider-free Feiyue iteration resume demo.")
    parser.add_argument("--root", required=True, help="Directory where demo artifacts will be written.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only.")
    args = parser.parse_args(argv)

    summary = run_demo(args.root)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(summary["resume_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
