from feiyue_core.recovery import RecoveryManifest
from feiyue_core.runtime import Reconciler, RecoveryPromptBuilder, SessionJournal
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
