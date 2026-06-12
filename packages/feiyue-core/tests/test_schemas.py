from datetime import datetime, timezone

from feiyue_core.schemas import (
    Candidate,
    CandidateStatus,
    ExecutionRun,
    ExecutionStatus,
    SkillCandidate,
    SkillCandidateStatus,
    StrategyVersion,
    TaskSpec,
    TaskStatus,
    TaskType,
    TraceEvent,
    TraceEventType,
    VerificationResult,
    VerifierType,
)


def test_task_spec_serializes_core_contract() -> None:
    task = TaskSpec(
        id="task_001",
        title="Fix failing tests",
        type=TaskType.CODE,
        status=TaskStatus.CREATED,
        goal="Make the toy repo test suite pass",
        acceptance_criteria=["pytest passes"],
        permissions={"read": True, "write": True, "execute": True},
        metadata={"repo": "toy"},
    )

    payload = task.model_dump(mode="json")

    assert payload["id"] == "task_001"
    assert payload["type"] == "code"
    assert payload["status"] == "created"
    assert payload["acceptance_criteria"] == ["pytest passes"]
    assert payload["permissions"]["execute"] is True
    assert payload["created_at"].endswith("Z")


def test_candidate_execution_verification_link_by_ids() -> None:
    candidate = Candidate(
        id="cand_001",
        task_id="task_001",
        status=CandidateStatus.GENERATED,
        strategy_version_id="strat_default",
        summary="Patch arithmetic helper",
        artifact_refs=["artifacts/candidates/cand_001.patch"],
    )
    run = ExecutionRun(
        id="run_001",
        candidate_id=candidate.id,
        status=ExecutionStatus.FINISHED,
        command="pytest tests/test_math.py -q",
        exit_code=0,
        duration_ms=125,
        artifact_refs=["artifacts/command-logs/run_001.log"],
    )
    result = VerificationResult(
        id="vr_001",
        execution_run_id=run.id,
        verifier_type=VerifierType.PYTEST,
        verifier_name="pytest",
        passed=True,
        score=1.0,
        evidence_refs=["artifacts/command-logs/run_001.log"],
    )

    assert candidate.model_dump(mode="json")["status"] == "generated"
    assert run.candidate_id == "cand_001"
    assert result.execution_run_id == "run_001"
    assert result.passed is True


def test_strategy_skill_and_trace_are_json_serializable() -> None:
    strategy = StrategyVersion(
        id="strat_default",
        name="default",
        config_hash="sha256:abc",
        prompt_refs=["prompts/default.md"],
        tool_policy={"allow": ["read_file", "terminal"]},
    )
    skill = SkillCandidate(
        id="skill_001",
        source_task_id="task_001",
        source_trace_id="trace_001",
        title="Fix assertion failures with minimal patches",
        applicability="Python unit test failures",
        content="Use pytest output to locate the failing assertion.",
        status=SkillCandidateStatus.PROPOSED,
    )
    event = TraceEvent(
        id="evt_001",
        session_id="sess_001",
        type=TraceEventType.TOOL_OPERATION_FINISHED,
        message="pytest passed",
        data={"exit_code": 0},
        timestamp=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )

    assert strategy.model_dump(mode="json")["tool_policy"]["allow"] == ["read_file", "terminal"]
    assert skill.model_dump(mode="json")["status"] == "proposed"
    assert event.model_dump(mode="json")["timestamp"] == "2026-06-12T00:00:00Z"
