import hashlib

from feiyue_core.recovery import OperationRiskLevel, RecoveryManifest
from feiyue_core.runtime import (
    OperationRecorder,
    Reconciler,
    RecoveryPromptBuilder,
    SessionJournal,
    SideEffectInspector,
)
from feiyue_core.runtime.resume_flow import ResumeFlow


def test_resume_flow_combines_reconciliation_and_recovery_prompt(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sess_resume_001",
            current_goal="resume interrupted task",
            confirmed_facts=["candidate patch was generated"],
            pending_operations=["op_push_001"],
            open_questions=["operation op_push_001 unknown: gateway restarted"],
            next_safe_action="inspect pending operations",
        )
    )

    result = ResumeFlow(
        journal=journal,
        reconciler=Reconciler(journal),
        prompt_builder=RecoveryPromptBuilder(),
    ).prepare()

    assert result.report.next_safe_action == "inspect pending/unknown operations before continuing"
    assert "op_push_001" in result.recovery_prompt
    assert "Pending / unknown operations" in result.recovery_prompt
    assert "inspect pending/unknown operations before continuing" in result.recovery_prompt

def test_resume_flow_persists_reconciled_confirmed_side_effects(tmp_path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("stable output\n", encoding="utf-8")
    expected_hash = hashlib.sha256(b"stable output\n").hexdigest()
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sess_resume_002",
            current_goal="resume interrupted write",
            pending_operations=["op_file_001"],
            side_effect_checks={
                "op_file_001": [
                    {"type": "file_hash", "path": str(artifact), "expected_sha256": expected_hash}
                ]
            },
        )
    )

    result = ResumeFlow(
        journal=journal,
        reconciler=Reconciler(journal, inspector=SideEffectInspector()),
        prompt_builder=RecoveryPromptBuilder(),
    ).prepare()
    persisted = journal.read_manifest()

    assert result.warnings == []
    assert "op_file_001" not in result.manifest.pending_operations
    assert "op_file_001" not in persisted.pending_operations
    assert "operation op_file_001 reconciled as confirmed" in persisted.verified_outputs
    assert result.report.next_safe_action == "continue with next planned step"


def test_resume_flow_recovers_interrupted_recorded_file_side_effect_after_restart(tmp_path) -> None:
    artifact = tmp_path / "artifact.txt"
    expected_hash = hashlib.sha256(b"stable output\n").hexdigest()
    journal = SessionJournal(tmp_path / "session.jsonl")
    recorder = OperationRecorder(journal)

    recorder.register(
        operation_id="op_file_002",
        tool="write_file",
        args={"path": str(artifact)},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"git_status": "clean"},
        side_effect_checks=[
            {"type": "file_hash", "path": str(artifact), "expected_sha256": expected_hash}
        ],
    )
    artifact.write_text("stable output\n", encoding="utf-8")

    # Simulate process/model restart: use a fresh ResumeFlow and no in-memory operation record.
    result = ResumeFlow(journal=journal).prepare()
    persisted = journal.read_manifest()

    assert result.warnings == []
    assert "op_file_002" not in persisted.pending_operations
    assert "operation op_file_002 reconciled as confirmed" in persisted.verified_outputs
    assert persisted.next_safe_action == "continue with next planned step"
    assert "## Pending / unknown operations\n- None" in result.recovery_prompt
