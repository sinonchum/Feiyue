from __future__ import annotations

import subprocess
from pathlib import Path

from feiyue_core.workflow import TaskContract
from feiyue_core.workflow.execution import CandidateFileWrite, WorkflowExecutionStatus, ToyWorkflowExecutor


def _init_toy_repo(path: Path) -> None:
    path.mkdir()
    (path / "pyproject.toml").write_text(
        """
[tool.pytest.ini_options]
pythonpath = ["."]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (path / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (path / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_adds_numbers():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)


def test_toy_workflow_executes_verified_patch_in_sandbox_without_mutating_source(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-success",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Escalate only after verifier failure.",
    )

    report = ToyWorkflowExecutor().execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.VERIFIED
    assert report.promotion_ready is True
    assert report.verification_passed is True
    assert report.changed_files == ["calc.py"]
    assert report.bug_dossier is None
    assert report.lesson_candidate is not None
    assert report.regression_check is not None
    assert report.regression_check.command == "python -m pytest -q"
    assert report.source_repo_clean is True
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    assert report.sandbox_removed is True


def test_toy_workflow_failure_generates_bug_dossier_and_rolls_back_sandbox(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-failure",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Escalate to teacher with a bug dossier after verifier failure.",
    )

    report = ToyWorkflowExecutor().execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.NEEDS_TEACHER
    assert report.promotion_ready is False
    assert report.verification_passed is False
    assert report.bug_dossier is not None
    assert report.bug_dossier.task_id == "m11-failure"
    assert report.bug_dossier.changed_files == ["calc.py"]
    assert report.bug_dossier.failing_command == "python -m pytest -q"
    assert "assert" in report.bug_dossier.error_excerpt
    assert report.lesson_candidate is None
    assert report.regression_check is None
    assert report.source_repo_clean is True
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    assert report.sandbox_removed is True


def test_toy_workflow_rejects_candidate_writes_outside_contract_scope(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-scope",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )

    report = ToyWorkflowExecutor().execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="README.md", content="out of scope\n")],
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.BLOCKED
    assert report.promotion_ready is False
    assert report.bug_dossier is not None
    assert "outside contract scope" in report.bug_dossier.error_excerpt
    assert report.source_repo_clean is True
    assert report.sandbox_removed is True





def test_toy_workflow_uses_fake_teacher_guidance_to_retry_and_pass(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-teacher-retry",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="After one verifier failure, request fake teacher guidance and retry once.",
    )

    report = ToyWorkflowExecutor().execute_with_teacher_retry(
        source_repo=repo,
        contract=contract,
        initial_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        teacher_guidance="Use addition, not multiplication, to satisfy the test.",
        revised_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.VERIFIED
    assert report.verification_passed is True
    assert report.promotion_ready is True
    assert report.attempt_count == 2
    assert len(report.teacher_guidance_events) == 1
    event = report.teacher_guidance_events[0]
    assert event.trigger == "verifier_failed"
    assert event.request_id == "teacher-request-m11-teacher-retry-1"
    assert event.guidance == "Use addition, not multiplication, to satisfy the test."
    assert report.bug_dossier is None
    assert report.lesson_candidate is not None
    assert report.lesson_candidate.source_task_id == "m11-teacher-retry"
    assert report.regression_check is not None
    assert report.source_repo_clean is True
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    assert report.sandbox_removed is True


def test_toy_workflow_teacher_retry_keeps_failure_when_revised_patch_fails(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-teacher-retry-fails",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Retry once after teacher guidance.",
    )

    report = ToyWorkflowExecutor().execute_with_teacher_retry(
        source_repo=repo,
        contract=contract,
        initial_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        teacher_guidance="Try a narrower patch, then stop after one retry.",
        revised_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a / b\n")],
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.NEEDS_TEACHER
    assert report.verification_passed is False
    assert report.promotion_ready is False
    assert report.attempt_count == 2
    assert len(report.teacher_guidance_events) == 1
    assert report.bug_dossier is not None
    assert report.bug_dossier.task_id == "m11-teacher-retry-fails"
    assert "retry" in report.bug_dossier.attempts
    assert report.lesson_candidate is None
    assert report.regression_check is None
    assert report.source_repo_clean is True
    assert report.sandbox_removed is True
