import hashlib
import subprocess

from feiyue_core.recovery import RecoveryManifest
from feiyue_core.runtime import Reconciler, ReconciliationDecision, SessionJournal, SideEffectInspector


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_reconciler_classifies_pending_unknown_operations_for_inspection(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sess_001",
            current_goal="resume safely",
            pending_operations=["op_api_001"],
            open_questions=["operation op_api_001 unknown: network interrupted"],
        )
    )

    report = Reconciler(journal).reconcile()

    assert report.decisions[0].operation_id == "op_api_001"
    assert report.decisions[0].decision == ReconciliationDecision.NEEDS_INSPECTION
    assert report.next_safe_action == "inspect pending/unknown operations before continuing"
    assert "op_api_001" in report.summary


def test_reconciler_marks_completed_operations_confirmed(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sess_002",
            current_goal="resume safely",
            completed_steps=["candidate cand_001 verification completed"],
            verified_outputs=["operation local_loop:task:cand finished"],
        )
    )

    report = Reconciler(journal).reconcile()

    assert report.decisions[0].operation_id == "operation local_loop:task:cand finished"
    assert report.decisions[0].decision == ReconciliationDecision.CONFIRMED
    assert report.next_safe_action == "continue with next planned step"


def test_reconciler_respects_do_not_repeat_as_unsafe(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sess_003",
            current_goal="resume safely",
            do_not_repeat=["do not repeat git push before checking remote head"],
        )
    )

    report = Reconciler(journal).reconcile()

    assert report.decisions[0].operation_id == "do_not_repeat:1"
    assert report.decisions[0].decision == ReconciliationDecision.UNSAFE_TO_REPEAT
    assert report.next_safe_action == "inspect pending/unknown operations before continuing"


def test_reconciler_reports_safe_to_continue_when_manifest_has_no_risks(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(RecoveryManifest(session_id="sess_004", current_goal="resume safely"))

    report = Reconciler(journal).reconcile()

    assert report.decisions == []
    assert report.next_safe_action == "continue with next planned step"
    assert report.summary == "No pending, unknown, or unsafe operations found."


def test_reconciler_confirms_pending_operation_when_file_side_effect_matches(tmp_path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("stable output\n", encoding="utf-8")
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sess_005",
            current_goal="resume safely",
            pending_operations=["op_file_001"],
            side_effect_checks={
                "op_file_001": [
                    {"type": "file_hash", "path": str(artifact), "expected_sha256": _sha256("stable output\n")}
                ]
            },
        )
    )

    report = Reconciler(journal, inspector=SideEffectInspector()).reconcile()

    assert report.decisions[0].operation_id == "op_file_001"
    assert report.decisions[0].decision == ReconciliationDecision.CONFIRMED
    assert "file hash matches" in report.decisions[0].reason
    assert report.next_safe_action == "continue with next planned step"


def test_reconciler_marks_pending_operation_unsafe_when_git_side_effect_mismatches(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sess_006",
            current_goal="resume safely",
            pending_operations=["op_git_001"],
            side_effect_checks={
                "op_git_001": [{"type": "git_ref", "repo_path": str(repo), "ref": "HEAD", "expected_sha": "deadbeef"}]
            },
        )
    )

    report = Reconciler(journal, inspector=SideEffectInspector()).reconcile()

    assert report.decisions[0].operation_id == "op_git_001"
    assert report.decisions[0].decision == ReconciliationDecision.UNSAFE_TO_REPEAT
    assert "git ref mismatch" in report.decisions[0].reason
