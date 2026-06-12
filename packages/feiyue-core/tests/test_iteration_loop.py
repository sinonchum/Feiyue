from __future__ import annotations

import json

from feiyue_core.audit import JsonlTraceWriter
from feiyue_core.generation import CandidateService, ToyIterationLoop
from feiyue_core.providers import FakeStudentProvider, FakeTeacherProvider, ModelProfile, ProviderRole
from feiyue_core.routing import ModelRoleRouter, TeacherInterventionPolicy
from feiyue_core.schemas import Candidate, CandidateStatus, StrategyVersion, TaskSpec, TaskStatus, TaskType, VerificationResult, VerifierType


class SequenceVerifier:
    def __init__(self, results: list[VerificationResult]) -> None:
        self.results = list(results)
        self.seen_candidates: list[str] = []

    def verify(self, candidate: Candidate) -> VerificationResult:
        self.seen_candidates.append(candidate.id)
        if not self.results:
            raise AssertionError("verifier called more times than expected")
        return self.results.pop(0)


def task_spec() -> TaskSpec:
    return TaskSpec(
        id="task_loop_001",
        title="Fix arithmetic helper",
        type=TaskType.CODE,
        status=TaskStatus.READY,
        goal="Make add return a + b",
        acceptance_criteria=["pytest passes", "candidate lineage is auditable"],
        metadata={"target_files": ["math_tools.py"], "constraints": ["Do not change tests"]},
    )


def strategy() -> StrategyVersion:
    return StrategyVersion(id="strategy_loop_v1", name="student-teacher loop", config_hash="hash_loop_v1")


def candidate_service() -> CandidateService:
    student = ModelProfile(provider="fake", model="fake-student-001", role=ProviderRole.STUDENT, cost_tier="low")
    teacher = ModelProfile(provider="fake", model="fake-teacher-001", role=ProviderRole.TEACHER, cost_tier="high")
    return CandidateService(
        router=ModelRoleRouter(
            student=student,
            teacher=teacher,
            teacher_policy=TeacherInterventionPolicy(max_student_failures_before_teacher=1),
        ),
        providers={ProviderRole.STUDENT: FakeStudentProvider(student), ProviderRole.TEACHER: FakeTeacherProvider(teacher)},
    )


def failed_pytest_result() -> VerificationResult:
    return VerificationResult(
        id="verify_fail_001",
        execution_run_id="run_loop_001",
        verifier_type=VerifierType.PYTEST,
        verifier_name="pytest",
        passed=False,
        confidence=0.9,
        failure_category="pytest_failure",
        metadata={"stdout": "E assert -1 == 3"},
    )


def passed_pytest_result() -> VerificationResult:
    return VerificationResult(
        id="verify_pass_001",
        execution_run_id="run_loop_002",
        verifier_type=VerifierType.PYTEST,
        verifier_name="pytest",
        passed=True,
        confidence=0.95,
        metadata={"stdout": "1 passed"},
    )


def test_toy_iteration_loop_revises_after_failure_with_sparse_teacher_guidance() -> None:
    loop = ToyIterationLoop(candidate_service=candidate_service(), verifier=SequenceVerifier([failed_pytest_result(), passed_pytest_result()]))

    result = loop.run(
        task=task_spec(),
        strategy=strategy(),
        initial_file_writes={"math_tools.py": "def add(a, b):\n    return -1\n"},
        revised_file_writes={"math_tools.py": "def add(a, b):\n    return a + b\n"},
        max_attempts=2,
    )

    assert result.passed is True
    assert result.final_candidate.status == CandidateStatus.VERIFIED
    assert len(result.candidates) == 2
    assert len(result.feedback) == 2
    assert len(result.teacher_guidance_events) == 1
    assert result.teacher_guidance_events[0]["kind"] == "teacher_guidance"

    first, revised = result.candidates
    assert revised.id != first.id
    assert revised.metadata["parent_candidate_id"] == first.id
    assert revised.metadata["revision_index"] == 1
    assert revised.metadata["feedback_category"] == "pytest_failure"
    assert revised.metadata["teacher_guidance"] == result.teacher_guidance_events[0]
    assert revised.metadata["teacher_trigger"] == "consecutive_student_failures"
    assert revised.metadata["verification_result_id"] == "verify_pass_001"


def test_toy_iteration_loop_stops_with_failed_candidate_when_attempt_budget_is_exhausted() -> None:
    loop = ToyIterationLoop(candidate_service=candidate_service(), verifier=SequenceVerifier([failed_pytest_result()]))

    result = loop.run(
        task=task_spec(),
        strategy=strategy(),
        initial_file_writes={"math_tools.py": "def add(a, b):\n    return -1\n"},
        revised_file_writes={"math_tools.py": "def add(a, b):\n    return a + b\n"},
        max_attempts=1,
    )

    assert result.passed is False
    assert result.final_candidate.status == CandidateStatus.FAILED
    assert len(result.candidates) == 1
    assert len(result.feedback) == 1
    assert result.teacher_guidance_events == []
    assert result.final_candidate.metadata["verification_result_id"] == "verify_fail_001"


def test_toy_iteration_loop_persists_auditable_jsonl_trace(tmp_path) -> None:
    trace_path = tmp_path / "iteration-trace.jsonl"
    loop = ToyIterationLoop(
        candidate_service=candidate_service(),
        verifier=SequenceVerifier([failed_pytest_result(), passed_pytest_result()]),
        trace_writer=JsonlTraceWriter(trace_path),
        session_id="sess_loop_trace_001",
    )

    result = loop.run(
        task=task_spec(),
        strategy=strategy(),
        initial_file_writes={"math_tools.py": "def add(a, b):\n    return -1\n"},
        revised_file_writes={"math_tools.py": "def add(a, b):\n    return a + b\n"},
        max_attempts=2,
    )

    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    event_types = [event["type"] for event in events]

    assert result.passed is True
    assert event_types == [
        "candidate_generated",
        "verification_failed",
        "feedback_analyzed",
        "teacher_guidance_requested",
        "candidate_revised",
        "verification_passed",
        "feedback_analyzed",
        "iteration_completed",
    ]
    assert all(event["session_id"] == "sess_loop_trace_001" for event in events)
    assert events[0]["data"]["candidate_id"] == result.candidates[0].id
    assert events[0]["data"]["prompt_rendered_hash"].startswith("sha256:")
    assert events[1]["data"]["verification_result_id"] == "verify_fail_001"
    assert events[3]["data"]["teacher_trigger"] == "consecutive_student_failures"
    assert events[4]["data"]["parent_candidate_id"] == result.candidates[0].id
    assert events[-1]["data"]["passed"] is True
    assert events[-1]["data"]["final_candidate_id"] == result.final_candidate.id
