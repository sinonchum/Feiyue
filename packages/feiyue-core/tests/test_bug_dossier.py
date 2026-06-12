from __future__ import annotations

from pydantic import ValidationError

from feiyue_core.workflow.bug_dossier import BugDossier


def test_bug_dossier_renders_deterministic_markdown() -> None:
    dossier = BugDossier(
        task_id="task-123",
        original_task="Fix the flaky verifier.",
        changed_files=["feiyue_core/verifiers/pytest_verifier.py", "tests/test_pytest_verifier.py"],
        failing_command="python -m pytest tests/test_pytest_verifier.py -q",
        error_excerpt="AssertionError: expected pass",
        attempts=["Adjusted timeout handling", "Re-ran targeted verifier tests"],
        suspected_cause="Verifier treats timeout as success.",
        teacher_request="Please confirm timeout semantics.",
    )

    assert dossier.render_markdown() == "\n".join(
        [
            "# Bug Dossier",
            "",
            "## Task ID",
            "task-123",
            "",
            "## Original Task",
            "Fix the flaky verifier.",
            "",
            "## Changed Files",
            "- feiyue_core/verifiers/pytest_verifier.py",
            "- tests/test_pytest_verifier.py",
            "",
            "## Failing Command",
            "`python -m pytest tests/test_pytest_verifier.py -q`",
            "",
            "## Error Excerpt",
            "```",
            "AssertionError: expected pass",
            "```",
            "",
            "## Attempts",
            "- Adjusted timeout handling",
            "- Re-ran targeted verifier tests",
            "",
            "## Suspected Cause",
            "Verifier treats timeout as success.",
            "",
            "## Request to Teacher",
            "Please confirm timeout semantics.",
        ]
    )


def test_bug_dossier_empty_lists_render_none() -> None:
    dossier = BugDossier(
        task_id="task-empty",
        original_task="Investigate failure.",
        changed_files=[],
        failing_command="pytest",
        error_excerpt="boom",
        attempts=[],
        suspected_cause="Unknown.",
        teacher_request="Need guidance.",
    )

    markdown = dossier.render_markdown()

    assert "## Changed Files\n- None" in markdown
    assert "## Attempts\n- None" in markdown


def test_bug_dossier_truncates_long_error_excerpt_with_configurable_limit() -> None:
    dossier = BugDossier(
        task_id="task-long",
        original_task="Fix noisy log.",
        changed_files=["x.py"],
        failing_command="pytest",
        error_excerpt="abcdef",
        attempts=["Collected log"],
        suspected_cause="Large traceback.",
        teacher_request="Help summarize.",
    )

    markdown = dossier.render_markdown(max_error_chars=3)

    assert "abc... [truncated 3 chars]" in markdown
    assert "abcdef" not in markdown


def test_bug_dossier_rejects_unknown_fields() -> None:
    try:
        BugDossier(
            task_id="task-123",
            original_task="Fix it.",
            changed_files=[],
            failing_command="pytest",
            error_excerpt="boom",
            attempts=[],
            suspected_cause="Unknown.",
            teacher_request="Help.",
            unexpected=True,
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("BugDossier should reject unknown fields")
