from feiyue_core.recovery import OperationRiskLevel, OperationStatus
from feiyue_core.runtime import OperationRecorder, SessionJournal


def test_operation_recorder_registers_before_side_effect(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)

    record = recorder.register(
        operation_id="op_write_001",
        tool="write_file",
        args={"path": "docs/example.md", "content": "hello"},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"git_status": "clean"},
    )

    assert record.operation_id == "op_write_001"
    assert record.status == OperationStatus.STARTED
    assert len(record.args_hash) == 64
    manifest = journal.read_manifest()
    assert manifest.pending_operations == ["op_write_001"]
    assert any(event.type == "tool_operation_started" for event in journal.read_all())


def test_operation_recorder_marks_finished_and_removes_pending(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    recorder.register(
        operation_id="op_git_001",
        tool="git_push",
        args={"remote": "origin", "branch": "main"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": "abc"},
    )

    finished = recorder.finish(
        operation_id="op_git_001",
        postconditions={"remote_head": "abc"},
        artifact_refs=["trace/events.jsonl"],
    )

    assert finished.status == OperationStatus.FINISHED
    assert journal.read_manifest().pending_operations == []
    assert journal.read_manifest().verified_outputs == ["operation op_git_001 finished"]
    assert any(event.type == "tool_operation_finished" for event in journal.read_all())


def test_operation_recorder_marks_unknown_for_recovery(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    recorder.register(
        operation_id="op_api_001",
        tool="github_api",
        args={"endpoint": "/repos/example"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"network": "available"},
    )

    unknown = recorder.mark_unknown("op_api_001", reason="process interrupted")

    assert unknown.status == OperationStatus.UNKNOWN
    manifest = journal.read_manifest()
    assert manifest.pending_operations == ["op_api_001"]
    assert "operation op_api_001 unknown: process interrupted" in manifest.open_questions
    assert any(event.type == "tool_operation_unknown" for event in journal.read_all())
