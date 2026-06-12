from datetime import datetime, timezone

from feiyue_core.recovery import (
    KnownMistake,
    MistakeScope,
    OperationRecord,
    OperationRiskLevel,
    OperationStatus,
    RecoveryManifest,
)


def test_recovery_manifest_captures_do_not_repeat_contract() -> None:
    manifest = RecoveryManifest(
        session_id="sess_001",
        task_id="task_001",
        current_goal="Resume code repair after fallback",
        active_project="/repo/toy",
        confirmed_facts=["pytest failed before fallback"],
        known_mistakes=["Do not rerun the same invalid patch"],
        do_not_repeat=["Do not push before checking remote HEAD"],
        completed_steps=["created candidate cand_001"],
        pending_operations=["op_001"],
        changed_files=["src/math.py"],
        verified_outputs=["pytest failure log captured"],
        next_safe_action="reconcile op_001 before making changes",
        updated_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )

    payload = manifest.model_dump(mode="json")

    assert payload["known_mistakes"] == ["Do not rerun the same invalid patch"]
    assert payload["do_not_repeat"] == ["Do not push before checking remote HEAD"]
    assert payload["pending_operations"] == ["op_001"]
    assert payload["updated_at"] == "2026-06-12T00:00:00Z"


def test_operation_record_requires_preconditions_for_side_effects() -> None:
    op = OperationRecord(
        operation_id="op_sess_001_0001",
        tool="write_file",
        args_hash="sha256:abcd",
        status=OperationStatus.STARTED,
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"path": "src/math.py", "sha256_before": "old"},
        postconditions={},
        artifact_refs=["artifacts/tool-results/op_sess_001_0001.json"],
    )

    payload = op.model_dump(mode="json")

    assert payload["status"] == "started"
    assert payload["risk_level"] == "medium"
    assert payload["preconditions"]["sha256_before"] == "old"


def test_known_mistake_is_scoped_and_evidence_backed() -> None:
    mistake = KnownMistake(
        mistake_id="m_001",
        summary="Fallback must not repeat an already failed patch strategy",
        evidence_ref="artifacts/model-errors/evt_123.json",
        scope=MistakeScope.TASK,
        severity=OperationRiskLevel.HIGH,
        created_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )

    payload = mistake.model_dump(mode="json")

    assert payload["scope"] == "task"
    assert payload["severity"] == "high"
    assert payload["evidence_ref"].startswith("artifacts/")
