from feiyue_core.recovery import RecoveryManifest
from feiyue_core.runtime import Reconciler, ReconciliationDecision, SessionJournal


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
