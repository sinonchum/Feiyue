from feiyue_core.recovery import RecoveryManifest
from feiyue_core.runtime.recovery_prompt import RecoveryPromptBuilder


def test_recovery_prompt_builder_includes_safety_sections() -> None:
    manifest = RecoveryManifest(
        session_id="sess_001",
        current_goal="continue Feiyue development",
        confirmed_facts=["local tests passed before restart"],
        known_mistakes=["python3 may not have pytest installed"],
        do_not_repeat=["do not rerun side-effecting push before checking git state"],
        pending_operations=["verify remote branch sync"],
        changed_files=["packages/feiyue-core/feiyue_core/runtime/journal.py"],
        verified_outputs=["15 tests passed"],
        open_questions=["whether native image routing should be forced"],
        next_safe_action="run git status and pytest with the active interpreter",
    )

    prompt = RecoveryPromptBuilder().build(manifest)

    assert "Confirmed facts" in prompt
    assert "Known mistakes" in prompt
    assert "Do not repeat" in prompt
    assert "Pending / unknown operations" in prompt
    assert "Next safe action" in prompt
    assert "python3 may not have pytest installed" in prompt
    assert "run git status and pytest with the active interpreter" in prompt


def test_recovery_prompt_builder_uses_explicit_none_for_empty_sections() -> None:
    manifest = RecoveryManifest(session_id="sess_002", current_goal="resume task")

    prompt = RecoveryPromptBuilder().build(manifest)

    assert "- None" in prompt
    assert "resume task" in prompt
