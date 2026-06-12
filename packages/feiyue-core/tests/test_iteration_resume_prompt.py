from __future__ import annotations

from feiyue_core.generation import IterationResumeContext, IterationResumePromptBuilder


def test_iteration_resume_prompt_builder_renders_fallback_prompt_with_do_not_repeat_rules() -> None:
    context = IterationResumeContext(
        session_id="sess_resume_001",
        task_id="task_resume_001",
        latest_candidate_id="cand_revised",
        parent_candidate_id="cand_initial",
        latest_verification_result_id="verify_fail_001",
        latest_feedback_category="pytest_failure",
        teacher_guidance_already_requested=True,
        completed=False,
        passed=False,
        next_safe_action="revise latest candidate using existing teacher guidance; do not request duplicate teacher guidance",
        candidate_lineage=["cand_initial", "cand_revised"],
        resume_summary="unresolved failure pytest_failure\nteacher guidance was already requested; do not request duplicate teacher guidance",
    )

    prompt = IterationResumePromptBuilder().build(context)

    assert "# Iteration Fallback Resume Prompt" in prompt
    assert "## Durable State Source" in prompt
    assert "Treat prior model chat context as disposable" in prompt
    assert "## Current Iteration State" in prompt
    assert "- Session ID: sess_resume_001" in prompt
    assert "- Task ID: task_resume_001" in prompt
    assert "- Latest candidate: cand_revised" in prompt
    assert "- Parent candidate: cand_initial" in prompt
    assert "- Candidate lineage: cand_initial -> cand_revised" in prompt
    assert "- Latest verification result: verify_fail_001" in prompt
    assert "- Latest feedback category: pytest_failure" in prompt
    assert "## Do Not Repeat" in prompt
    assert "- Do not request duplicate teacher guidance; it was already requested." in prompt
    assert "- Do not mark success until an external verifier passes." in prompt
    assert "## Next Safe Action" in prompt
    assert "revise latest candidate using existing teacher guidance" in prompt
    assert "## Resume Summary" in prompt
    assert "unresolved failure pytest_failure" in prompt


def test_iteration_resume_prompt_builder_renders_none_for_missing_fields() -> None:
    context = IterationResumeContext(
        next_safe_action="inspect trace and rebuild missing iteration state before continuing",
        resume_summary="trace is incomplete",
    )

    prompt = IterationResumePromptBuilder().build(context)

    assert "- Session ID: None" in prompt
    assert "- Task ID: None" in prompt
    assert "- Latest candidate: None" in prompt
    assert "- Parent candidate: None" in prompt
    assert "- Candidate lineage: None" in prompt
    assert "- Latest verification result: None" in prompt
    assert "- Latest feedback category: None" in prompt
    assert "- Teacher guidance already requested: False" in prompt
    assert "- Completed: False" in prompt
    assert "- Passed: False" in prompt
    assert "## Do Not Repeat" in prompt
    assert "- None" in prompt


def test_iteration_resume_prompt_builder_for_completed_success_points_to_acceptance_gate() -> None:
    context = IterationResumeContext(
        session_id="sess_resume_002",
        task_id="task_resume_002",
        latest_candidate_id="cand_verified",
        latest_verification_result_id="verify_pass_001",
        latest_feedback_category="passed",
        completed=True,
        passed=True,
        next_safe_action="promote verified candidate or run next acceptance gate",
        candidate_lineage=["cand_verified"],
        resume_summary="passed: True",
    )

    prompt = IterationResumePromptBuilder().build(context)

    assert "- Latest candidate: cand_verified" in prompt
    assert "- Completed: True" in prompt
    assert "- Passed: True" in prompt
    assert "- promote verified candidate or run next acceptance gate" in prompt
    assert "Do not regenerate a new candidate before checking whether promotion/acceptance is sufficient." in prompt
