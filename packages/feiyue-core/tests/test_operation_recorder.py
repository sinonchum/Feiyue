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


def test_operation_recorder_persists_side_effect_checks_on_register(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    target = tmp_path / "output.txt"

    recorder.register(
        operation_id="op_file_001",
        tool="write_file",
        args={"path": str(target)},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"git_status": "clean"},
        side_effect_checks=[
            {"type": "file_hash", "path": str(target), "expected_sha256": "abc123"}
        ],
    )

    manifest = journal.read_manifest()
    assert manifest.pending_operations == ["op_file_001"]
    assert manifest.side_effect_checks == {
        "op_file_001": [
            {"type": "file_hash", "path": str(target), "expected_sha256": "abc123"}
        ]
    }


def test_operation_recorder_auto_derives_file_hash_check_for_write_file_content(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    target = tmp_path / "auto.txt"

    recorder.register(
        operation_id="op_write_auto_001",
        tool="write_file",
        args={"path": str(target), "content": "stable output\n"},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"git_status": "clean"},
    )

    checks = journal.read_manifest().side_effect_checks["op_write_auto_001"]
    assert checks == [
        {
            "type": "file_hash",
            "path": str(target),
            "expected_sha256": "3eba90a91b7866839db6633908b0c1ed87076e73685e448456af07efb2c2bf5a",
        }
    ]


def test_operation_recorder_removes_side_effect_checks_after_finish(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    target = tmp_path / "finished.txt"
    recorder.register(
        operation_id="op_write_finished_001",
        tool="write_file",
        args={"path": str(target), "content": "done\n"},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"git_status": "clean"},
    )

    recorder.finish("op_write_finished_001", postconditions={"passed": True})

    manifest = journal.read_manifest()
    assert manifest.pending_operations == []
    assert "op_write_finished_001" not in manifest.side_effect_checks


def test_operation_recorder_auto_derives_git_ref_check(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)

    recorder.register(
        operation_id="op_git_auto_001",
        tool="git_push",
        args={"repo_path": str(tmp_path), "ref": "refs/remotes/origin/main", "expected_sha": "abc123"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": "abc123"},
    )

    checks = journal.read_manifest().side_effect_checks["op_git_auto_001"]
    assert checks == [
        {"type": "git_ref", "repo_path": str(tmp_path), "ref": "refs/remotes/origin/main", "expected_sha": "abc123"}
    ]


def test_operation_recorder_auto_derives_artifact_exists_check(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)
    artifact = tmp_path / "report.json"

    recorder.register(
        operation_id="op_artifact_auto_001",
        tool="generate_artifact",
        args={"artifact_path": str(artifact)},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"task_id": "task_001"},
    )

    checks = journal.read_manifest().side_effect_checks["op_artifact_auto_001"]
    assert checks == [{"type": "artifact_exists", "path": str(artifact)}]


def test_operation_recorder_auto_derives_git_remote_ref_check(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)

    recorder.register(
        operation_id="op_git_remote_auto_001",
        tool="git_push",
        args={"remote_url": "file:///tmp/remote.git", "remote_ref": "refs/heads/main", "expected_sha": "abc123"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": "abc123"},
    )

    checks = journal.read_manifest().side_effect_checks["op_git_remote_auto_001"]
    assert checks == [
        {
            "type": "git_remote_ref",
            "remote_url": "file:///tmp/remote.git",
            "ref": "refs/heads/main",
            "expected_sha": "abc123",
        }
    ]


def test_operation_recorder_auto_derives_github_ref_check(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)

    recorder.register(
        operation_id="op_github_ref_auto_001",
        tool="github_api",
        args={"github_repo": "sinonchum/Feiyue", "ref": "refs/heads/main", "expected_sha": "abc123"},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"request": "sent"},
    )

    checks = journal.read_manifest().side_effect_checks["op_github_ref_auto_001"]
    assert checks == [
        {"type": "github_ref", "repo": "sinonchum/Feiyue", "ref": "refs/heads/main", "expected_sha": "abc123"}
    ]
