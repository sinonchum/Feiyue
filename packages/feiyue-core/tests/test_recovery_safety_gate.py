from feiyue_core.recovery import OperationRiskLevel, RecoveryManifest
from feiyue_core.runtime import OperationRecorder, RecoverySafetyGate, SessionJournal


def test_operation_recorder_persists_operation_risk_levels(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)

    recorder.register(
        operation_id="op_push_001",
        tool="git_push",
        args={"remote": "origin", "branch": "main"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": "abc"},
    )

    manifest = journal.read_manifest()
    assert manifest.operation_risk_levels == {"op_push_001": "high"}


def test_recovery_safety_gate_blocks_unresolved_high_risk_pending_operation(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    recorder.register(
        operation_id="op_push_002",
        tool="git_push",
        args={"remote": "origin", "branch": "main"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": "abc"},
    )
    recorder.mark_unknown("op_push_002", reason="network interrupted after request was sent")

    decision = RecoverySafetyGate().evaluate(journal.read_manifest())

    assert decision.allowed is False
    assert decision.blocked_operations == ["op_push_002"]
    assert "high-risk pending/unknown side effect" in decision.reason


def test_recovery_safety_gate_allows_medium_risk_pending_operation(tmp_path) -> None:
    manifest = RecoveryManifest(
        session_id="sess_safe_001",
        current_goal="resume",
        pending_operations=["op_medium_001"],
        operation_risk_levels={"op_medium_001": "medium"},
    )

    decision = RecoverySafetyGate().evaluate(manifest)

    assert decision.allowed is True
    assert decision.blocked_operations == []


def test_recovery_safety_gate_allows_after_high_risk_operation_is_confirmed(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    recorder.register(
        operation_id="op_push_003",
        tool="git_push",
        args={"remote": "origin", "branch": "main"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": "abc"},
    )
    recorder.finish("op_push_003", postconditions={"remote_head": "abc"})

    decision = RecoverySafetyGate().evaluate(journal.read_manifest())

    assert decision.allowed is True
    assert decision.blocked_operations == []
    assert "op_push_003" not in journal.read_manifest().operation_risk_levels


def test_resume_flow_blocks_high_risk_unknown_side_effect(tmp_path) -> None:
    from feiyue_core.runtime import ResumeFlow

    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    recorder.register(
        operation_id="op_push_004",
        tool="git_push",
        args={"remote": "origin", "branch": "main"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": "abc"},
    )
    recorder.mark_unknown("op_push_004", reason="network interrupted after request was sent")

    result = ResumeFlow(journal=journal).prepare()
    persisted = journal.read_manifest()

    assert result.safety_decision is not None
    assert result.safety_decision.allowed is False
    assert result.safety_decision.blocked_operations == ["op_push_004"]
    assert persisted.next_safe_action == "resolve high-risk pending/unknown side effects before continuing"
    assert "blocked high-risk pending/unknown side effect operations: op_push_004" in result.warnings
