from __future__ import annotations

import json
import subprocess
from pathlib import Path

from feiyue_core.safety import (
    GovernanceAction,
    HumanApprovalRecord,
    PolicyDecisionReason,
    PolicyGovernor,
    PolicyGovernorConfig,
    RiskLevel,
)
from feiyue_core.workflow import TaskContract
from feiyue_core.workflow.execution import (
    CandidateFileWrite,
    PromotionStatus,
    RunEvidenceLoader,
    RunEvidenceNotFoundError,
    RunCatalog,
    WorkflowExecutionStatus,
    ToyWorkflowExecutor,
    WorkflowReportWriter,
)
from feiyue_core.workflow.profile_worker_bridge import (
    ProfileWorkflowBridge,
    ProfileWorkflowBridgeAuthorization,
    ProfileWorkflowBridgeStatus,
)
from feiyue_core.workflow.real_profile_workflow_runner import (
    RealProfileWorkflowAuthorization,
    RealProfileWorkflowRunner,
    RealProfileWorkflowStatus,
)
from feiyue_core.providers.profile_runner import FakeProfileRunner, ProfileRunResult


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



def test_toy_workflow_multi_round_fake_teacher_retry_passes_on_second_retry(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-teacher-multi-pass",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Bound retries; each fake teacher hint must still be verifier-gated.",
    )

    report = ToyWorkflowExecutor().execute_with_teacher_retry(
        source_repo=repo,
        contract=contract,
        initial_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        teacher_guidance=[
            "Multiplication is wrong, try a safer arithmetic operator.",
            "Use addition exactly; success must come from pytest.",
        ],
        revised_writes=[
            [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a / b\n")],
            [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        ],
        max_attempts=3,
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.VERIFIED
    assert report.verification_passed is True
    assert report.promotion_ready is True
    assert report.attempt_count == 3
    assert report.bug_dossier is None
    assert len(report.teacher_guidance_events) == 2
    assert [event.request_id for event in report.teacher_guidance_events] == [
        "teacher-request-m11-teacher-multi-pass-1",
        "teacher-request-m11-teacher-multi-pass-2",
    ]
    assert [event.attempt_index for event in report.teacher_guidance_events] == [2, 3]
    assert len(report.attempt_evidence) == 3
    assert [attempt.attempt_index for attempt in report.attempt_evidence] == [1, 2, 3]
    assert [attempt.verification_passed for attempt in report.attempt_evidence] == [False, False, True]
    assert report.attempt_evidence[1].teacher_request_id == "teacher-request-m11-teacher-multi-pass-1"
    assert report.attempt_evidence[2].teacher_request_id == "teacher-request-m11-teacher-multi-pass-2"
    assert report.attempt_evidence[2].failure_reason is None
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"



def test_toy_workflow_multi_round_fake_teacher_retry_stops_when_budget_exhausted(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-teacher-multi-fail",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Stop after bounded fake teacher retries and hand off safely.",
    )

    report = ToyWorkflowExecutor().execute_with_teacher_retry(
        source_repo=repo,
        contract=contract,
        initial_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        teacher_guidance=["Try division.", "Try subtraction."],
        revised_writes=[
            [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a / b\n")],
            [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a - b\n")],
            [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        ],
        max_attempts=3,
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.NEEDS_TEACHER
    assert report.verification_passed is False
    assert report.promotion_ready is False
    assert report.attempt_count == 3
    assert len(report.teacher_guidance_events) == 2
    assert len(report.attempt_evidence) == 3
    assert [attempt.verification_passed for attempt in report.attempt_evidence] == [False, False, False]
    assert report.bug_dossier is not None
    assert report.bug_dossier.task_id == "m11-teacher-multi-fail"
    assert "retry_1" in report.bug_dossier.attempts
    assert "retry_2" in report.bug_dossier.attempts
    assert "maximum fake teacher retry attempts exhausted" in report.bug_dossier.teacher_request
    assert report.lesson_candidate is None
    assert report.regression_check is None
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"



def test_promotes_verified_patch_to_target_branch_without_mutating_current_checkout(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-promotion",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor()
    report = executor.execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=writes,
        project_name="toy-calculator",
    )

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="feiyue/m11-promotion",
        commit_message="feat: promote verified calculator fix",
    )

    assert promotion.status == PromotionStatus.PROMOTED
    assert promotion.target_branch == "feiyue/m11-promotion"
    assert promotion.commit_sha
    assert promotion.promoted_files == ["calc.py"]
    assert promotion.source_repo_clean is True
    assert promotion.promotion_worktree_removed is True
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    branch_content = subprocess.run(
        ["git", "show", "feiyue/m11-promotion:calc.py"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert branch_content == "def add(a, b):\n    return a + b\n"


def test_promotion_blocks_unverified_report_and_leaves_repo_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-promotion-blocked",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")]
    executor = ToyWorkflowExecutor()
    report = executor.execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=writes,
        project_name="toy-calculator",
    )

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="feiyue/should-not-exist",
        commit_message="feat: should not promote",
    )

    assert promotion.status == PromotionStatus.BLOCKED
    assert promotion.commit_sha is None
    assert promotion.reason == "report is not promotion-ready"
    assert promotion.source_repo_clean is True
    assert promotion.promotion_worktree_removed is True
    refs = subprocess.run(
        ["git", "branch", "--list", "feiyue/should-not-exist"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert refs.strip() == ""
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"



def test_workflow_report_writer_persists_execution_teacher_and_promotion_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-report-success",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor()
    report = executor.execute_with_teacher_retry(
        source_repo=repo,
        contract=contract,
        initial_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        teacher_guidance="Use addition after verifier failure.",
        revised_writes=writes,
        project_name="toy-calculator",
    )
    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="feiyue/m11-report-success",
        commit_message="feat: promote report success",
    )

    artifacts = WorkflowReportWriter(repo).write(report=report, promotion=promotion)

    run_dir = repo / ".hermes" / "runs" / "m11-report-success"
    assert artifacts.run_dir == run_dir
    assert artifacts.execution_json_path == run_dir / "execution-report.json"
    assert artifacts.execution_markdown_path == run_dir / "execution-report.md"
    assert artifacts.teacher_guidance_markdown_path == run_dir / "teacher-guidance.md"
    assert artifacts.promotion_json_path == run_dir / "promotion-result.json"
    assert artifacts.promotion_markdown_path == run_dir / "promotion-result.md"
    assert artifacts.bug_dossier_markdown_path is None
    assert artifacts.execution_json_path.exists()
    assert "m11-report-success" in artifacts.execution_json_path.read_text(encoding="utf-8")
    assert "# Workflow Execution Report" in artifacts.execution_markdown_path.read_text(encoding="utf-8")
    assert "Use addition after verifier failure." in artifacts.teacher_guidance_markdown_path.read_text(encoding="utf-8")
    assert "feiyue/m11-report-success" in artifacts.promotion_markdown_path.read_text(encoding="utf-8")


def test_workflow_report_writer_persists_bug_dossier_for_failed_execution(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m11-report-failure",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    report = ToyWorkflowExecutor().execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        project_name="toy-calculator",
    )

    artifacts = WorkflowReportWriter(repo).write(report=report)

    run_dir = repo / ".hermes" / "runs" / "m11-report-failure"
    assert artifacts.run_dir == run_dir
    assert artifacts.bug_dossier_markdown_path == run_dir / "bug-dossier.md"
    assert artifacts.teacher_guidance_markdown_path is None
    assert artifacts.promotion_json_path is None
    assert artifacts.bug_dossier_markdown_path.exists()
    bug_text = artifacts.bug_dossier_markdown_path.read_text(encoding="utf-8")
    assert "# Bug Dossier" in bug_text
    assert "m11-report-failure" in bug_text
    assert "python -m pytest -q" in bug_text



def test_policy_governor_allows_low_risk_workflow_execution(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-exec-policy-allow",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )

    report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.LOW,
        estimated_tokens=500,
    )

    assert report.status == WorkflowExecutionStatus.VERIFIED
    assert report.policy_decision is not None
    assert report.policy_decision.action == GovernanceAction.ALLOW
    assert report.policy_decision.reason == PolicyDecisionReason.WITHIN_POLICY


def test_policy_governor_blocks_teacher_retry_when_budget_exhausted(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-teacher-policy-block",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    executor = ToyWorkflowExecutor(
        policy_governor=PolicyGovernor(PolicyGovernorConfig(max_teacher_calls=0))
    )

    report = executor.execute_with_teacher_retry(
        source_repo=repo,
        contract=contract,
        initial_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        teacher_guidance="This guidance must not be applied when budget is exhausted.",
        revised_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        teacher_calls_used=0,
    )

    assert report.status == WorkflowExecutionStatus.NEEDS_TEACHER
    assert report.attempt_count == 1
    assert report.teacher_guidance_events == []
    assert report.policy_decision is not None
    assert report.policy_decision.action == GovernanceAction.BLOCK
    assert report.policy_decision.reason == PolicyDecisionReason.TEACHER_CALL_BUDGET_EXHAUSTED
    assert report.bug_dossier is not None
    assert "policy_gate" in report.bug_dossier.attempts
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"


def test_policy_governor_escalates_high_risk_promotion_before_branch_creation(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-promotion-policy-escalate",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor(policy_governor=PolicyGovernor())
    report = executor.execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=writes,
        project_name="toy-calculator",
    )

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="feiyue/m12-policy-escalated",
        commit_message="feat: should require approval",
        risk_level=RiskLevel.HIGH,
    )

    assert promotion.status == PromotionStatus.BLOCKED
    assert promotion.commit_sha is None
    assert promotion.reason == "high_risk_operation"
    assert promotion.policy_decision is not None
    assert promotion.policy_decision.action == GovernanceAction.ESCALATE
    assert promotion.policy_decision.requires_human_approval is True
    refs = subprocess.run(
        ["git", "branch", "--list", "feiyue/m12-policy-escalated"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert refs.strip() == ""
    assert promotion.source_repo_clean is True
    assert promotion.promotion_worktree_removed is True



def test_workflow_report_writer_persists_execution_policy_decision_markdown(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-report-policy-execution",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.LOW,
        estimated_tokens=640,
    )

    artifacts = WorkflowReportWriter(repo).write(report=report)

    markdown = artifacts.execution_markdown_path.read_text(encoding="utf-8")
    assert "## Policy Decision" in markdown
    assert "- action: allow" in markdown
    assert "- reason: within_policy" in markdown
    assert "- operation: candidate_execution" in markdown
    assert "- estimated_tokens: 640" in markdown


def test_workflow_report_writer_persists_promotion_policy_decision_markdown(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-report-policy-promotion",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor(policy_governor=PolicyGovernor())
    report = executor.execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=writes,
        project_name="toy-calculator",
    )
    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="feiyue/m12-report-policy-promotion",
        commit_message="feat: should not promote without approval",
        risk_level=RiskLevel.HIGH,
    )

    artifacts = WorkflowReportWriter(repo).write(report=report, promotion=promotion)

    markdown = artifacts.promotion_markdown_path.read_text(encoding="utf-8")
    assert "## Policy Decision" in markdown
    assert "- action: escalate" in markdown
    assert "- reason: high_risk_operation" in markdown
    assert "- operation: promotion" in markdown
    assert "- requires_human_approval: True" in markdown



def test_policy_blocked_candidate_execution_records_no_execution_side_effect(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-evidence-execution-block",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )

    report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.HIGH,
    )

    assert report.status == WorkflowExecutionStatus.BLOCKED
    assert report.execution_performed is False
    assert report.retry_performed is False
    assert report.sandbox_removed is True
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
    artifacts = WorkflowReportWriter(repo).write(report=report)
    markdown = artifacts.execution_markdown_path.read_text(encoding="utf-8")
    assert "## Action Evidence" in markdown
    assert "- execution_performed: False" in markdown
    assert "- retry_performed: False" in markdown


def test_policy_blocked_teacher_retry_records_retry_not_performed(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-evidence-teacher-block",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    executor = ToyWorkflowExecutor(
        policy_governor=PolicyGovernor(PolicyGovernorConfig(max_teacher_calls=0))
    )

    report = executor.execute_with_teacher_retry(
        source_repo=repo,
        contract=contract,
        initial_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")],
        teacher_guidance="Do not apply when blocked.",
        revised_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
    )

    assert report.status == WorkflowExecutionStatus.NEEDS_TEACHER
    assert report.execution_performed is True
    assert report.retry_performed is False
    artifacts = WorkflowReportWriter(repo).write(report=report)
    markdown = artifacts.execution_markdown_path.read_text(encoding="utf-8")
    assert "## Action Evidence" in markdown
    assert "- execution_performed: True" in markdown
    assert "- retry_performed: False" in markdown


def test_policy_escalated_promotion_records_no_side_effect_performed(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-evidence-promotion-block",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor(policy_governor=PolicyGovernor())
    report = executor.execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=writes,
        project_name="toy-calculator",
    )

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="feiyue/m12-evidence-promotion-block",
        commit_message="feat: should not promote",
        risk_level=RiskLevel.HIGH,
    )

    assert promotion.status == PromotionStatus.BLOCKED
    assert promotion.side_effect_performed is False
    assert promotion.promotion_worktree_removed is True
    artifacts = WorkflowReportWriter(repo).write(report=report, promotion=promotion)
    markdown = artifacts.promotion_markdown_path.read_text(encoding="utf-8")
    assert "## Action Evidence" in markdown
    assert "- side_effect_performed: False" in markdown



def test_workflow_report_writer_persists_run_evidence_index_for_policy_block(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-index-policy-block",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.HIGH,
    )

    artifacts = WorkflowReportWriter(repo).write(report=report)

    assert artifacts.run_evidence_json_path == repo / ".hermes" / "runs" / "m12-index-policy-block" / "run-evidence.json"
    data = json.loads(artifacts.run_evidence_json_path.read_text(encoding="utf-8"))
    assert data["task_id"] == "m12-index-policy-block"
    assert data["status"] == "blocked"
    assert data["policy_action"] == "escalate"
    assert data["policy_reason"] == "high_risk_operation"
    assert data["execution_performed"] is False
    assert data["retry_performed"] is False
    assert data["promotion_side_effect_performed"] is None
    assert data["safe_to_retry"] is False
    assert data["next_safe_action"] == "request_human_approval"
    assert data["report_paths"]["execution_report"] == "execution-report.md"


def test_workflow_report_writer_persists_run_evidence_index_for_promoted_patch(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-index-promoted",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor(policy_governor=PolicyGovernor())
    report = executor.execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=writes,
        project_name="toy-calculator",
    )
    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="feiyue/m12-index-promoted",
        commit_message="feat: promote indexed patch",
    )

    artifacts = WorkflowReportWriter(repo).write(report=report, promotion=promotion)

    data = json.loads(artifacts.run_evidence_json_path.read_text(encoding="utf-8"))
    assert data["task_id"] == "m12-index-promoted"
    assert data["status"] == "verified"
    assert data["promotion_status"] == "promoted"
    assert data["promotion_side_effect_performed"] is True
    assert data["safe_to_retry"] is False
    assert data["next_safe_action"] == "record_lesson_or_continue"
    assert data["report_paths"]["promotion_result"] == "promotion-result.md"



def test_run_evidence_loader_loads_index_and_renders_fallback_handoff(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-loader-policy-block",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.HIGH,
    )
    WorkflowReportWriter(repo).write(report=report)

    loader = RunEvidenceLoader(repo)
    evidence = loader.load("m12-loader-policy-block")
    summary = loader.render_handoff_summary("m12-loader-policy-block")

    assert evidence.task_id == "m12-loader-policy-block"
    assert evidence.safe_to_retry is False
    assert evidence.next_safe_action == "request_human_approval"
    assert "# Fallback Handoff Summary" in summary
    assert "- task_id: m12-loader-policy-block" in summary
    assert "- safe_to_retry: False" in summary
    assert "- next_safe_action: request_human_approval" in summary
    assert "- policy_reason: high_risk_operation" in summary
    assert "- execution_report: execution-report.md" in summary


def test_run_evidence_loader_missing_index_raises_typed_error(tmp_path: Path) -> None:
    loader = RunEvidenceLoader(tmp_path)

    try:
        loader.load("missing-task")
    except RunEvidenceNotFoundError as exc:
        assert exc.task_id == "missing-task"
        assert exc.path == tmp_path / ".hermes" / "runs" / "missing-task" / "run-evidence.json"
        assert "missing-task" in str(exc)
    else:
        raise AssertionError("Expected RunEvidenceNotFoundError")


def test_workflow_report_writer_persists_approval_evidence_for_handoff(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-approval-handoff",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.HIGH,
    )
    approval = HumanApprovalRecord(
        approval_id="approval-m12-001",
        task_id="m12-approval-handoff",
        approved_action="candidate_execution",
        approver="Simon",
        approved_at="2026-06-13T12:00:00Z",
        reason="Approve exact blocked candidate execution after review.",
    )

    artifacts = WorkflowReportWriter(repo).write(report=report, approval=approval)

    assert artifacts.approval_json_path == repo / ".hermes" / "runs" / "m12-approval-handoff" / "approval.json"
    approval_data = json.loads(artifacts.approval_json_path.read_text(encoding="utf-8"))
    assert approval_data == {
        "approval_id": "approval-m12-001",
        "task_id": "m12-approval-handoff",
        "approved_action": "candidate_execution",
        "approver": "Simon",
        "approved_at": "2026-06-13T12:00:00Z",
        "reason": "Approve exact blocked candidate execution after review.",
    }
    evidence = json.loads(artifacts.run_evidence_json_path.read_text(encoding="utf-8"))
    assert evidence["approval_exists"] is True
    assert evidence["approval_id"] == "approval-m12-001"
    assert evidence["approval_approver"] == "Simon"
    assert evidence["approval_action"] == "candidate_execution"
    assert evidence["approval_applies"] is True
    assert evidence["report_paths"]["approval"] == "approval.json"

    loaded_approval = RunEvidenceLoader(repo).load_approval("m12-approval-handoff")
    summary = RunEvidenceLoader(repo).render_handoff_summary("m12-approval-handoff")

    assert loaded_approval == approval
    assert "## Approval Evidence" in summary
    assert "- approval_exists: True" in summary
    assert "- approval_id: approval-m12-001" in summary
    assert "- approval_approver: Simon" in summary
    assert "- approval_action: candidate_execution" in summary
    assert "- approval_applies: True" in summary
    assert "- approval: approval.json" in summary


def test_run_evidence_handoff_marks_missing_approval_explicitly(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="m12-approval-missing",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.HIGH,
    )
    WorkflowReportWriter(repo).write(report=report)

    loader = RunEvidenceLoader(repo)
    evidence = loader.load("m12-approval-missing")
    summary = loader.render_handoff_summary("m12-approval-missing")

    assert evidence.approval_exists is False
    assert evidence.approval_id is None
    assert evidence.approval_applies is False
    assert loader.load_approval("m12-approval-missing") is None
    assert "## Approval Evidence" in summary
    assert "- approval_exists: False" in summary
    assert "- approval_id: None" in summary
    assert "- approval_applies: False" in summary


def test_run_catalog_lists_summaries_and_aggregates_next_actions(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract_block = TaskContract(
        task_id="m13-catalog-block",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    blocked_report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract_block,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
        risk_level=RiskLevel.HIGH,
    )
    WorkflowReportWriter(repo).write(report=blocked_report)

    contract_verified = TaskContract(
        task_id="m13-catalog-verified",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    verified_report = ToyWorkflowExecutor(policy_governor=PolicyGovernor()).execute(
        source_repo=repo,
        contract=contract_verified,
        candidate_writes=[CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")],
        project_name="toy-calculator",
    )
    WorkflowReportWriter(repo).write(report=verified_report)

    summary = RunCatalog(repo).summary()

    assert summary.total_runs == 2
    assert summary.safe_to_retry_count == 0
    assert summary.next_action_counts == {
        "promote_verified_patch": 1,
        "request_human_approval": 1,
    }
    assert [run.task_id for run in summary.runs] == ["m13-catalog-block", "m13-catalog-verified"]
    assert summary.runs[0].status == "blocked"
    assert summary.runs[0].policy_reason == "high_risk_operation"
    assert summary.runs[0].approval_exists is False


def test_run_catalog_returns_empty_summary_when_no_runs_exist(tmp_path: Path) -> None:
    summary = RunCatalog(tmp_path).summary()

    assert summary.total_runs == 0
    assert summary.safe_to_retry_count == 0
    assert summary.next_action_counts == {}
    assert summary.runs == []


def test_profile_workflow_bridge_executes_profile_generated_patch_in_sandbox(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="w42-profile-worker-pass",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        acceptance_criteria=["pytest passes"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Run weak profile once; verifier decides success.",
    )
    fake_runner = FakeProfileRunner(
        {
            "feiyue-weak-deepseek-flash": json.dumps(
                {"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]}
            )
        }
    )

    bridge_report = ProfileWorkflowBridge(profile_runner=fake_runner).execute(
        source_repo=repo,
        contract=contract,
        project_name="toy-calculator",
        worker_profile="feiyue-weak-deepseek-flash",
        authorization=ProfileWorkflowBridgeAuthorization(scopes=["profile_workflow_execute"], max_profile_calls=1),
    )

    assert bridge_report.status == ProfileWorkflowBridgeStatus.VERIFIED
    assert bridge_report.provider_call_count == 1
    assert bridge_report.worker_profile == "feiyue-weak-deepseek-flash"
    assert bridge_report.reason_codes == ["profile_workflow_execute_authorized", "profile_runner_injected"]
    assert bridge_report.workflow_report.status == WorkflowExecutionStatus.VERIFIED
    assert bridge_report.workflow_report.promotion_ready is True
    assert bridge_report.workflow_report.changed_files == ["calc.py"]
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"


def test_profile_workflow_bridge_blocks_without_execute_authorization(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="w42-profile-worker-blocked",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    fake_runner = FakeProfileRunner(
        {"feiyue-weak-deepseek-flash": json.dumps({"writes": [{"path": "calc.py", "content": "ignored"}]})}
    )

    bridge_report = ProfileWorkflowBridge(profile_runner=fake_runner).execute(
        source_repo=repo,
        contract=contract,
        project_name="toy-calculator",
        worker_profile="feiyue-weak-deepseek-flash",
        authorization=ProfileWorkflowBridgeAuthorization(scopes=["profile_workflow_plan"], max_profile_calls=1),
    )

    assert bridge_report.status == ProfileWorkflowBridgeStatus.BLOCKED
    assert bridge_report.provider_call_count == 0
    assert bridge_report.workflow_report is None
    assert bridge_report.reason_codes == ["authorization_scope_profile_workflow_execute_missing"]
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"


def test_profile_workflow_bridge_blocks_when_profile_output_is_not_candidate_writes(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="w42-profile-worker-invalid-json",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )
    fake_runner = FakeProfileRunner({"feiyue-weak-deepseek-flash": "not json"})

    bridge_report = ProfileWorkflowBridge(profile_runner=fake_runner).execute(
        source_repo=repo,
        contract=contract,
        project_name="toy-calculator",
        worker_profile="feiyue-weak-deepseek-flash",
        authorization=ProfileWorkflowBridgeAuthorization(scopes=["profile_workflow_execute"], max_profile_calls=1),
    )

    assert bridge_report.status == ProfileWorkflowBridgeStatus.BLOCKED
    assert bridge_report.provider_call_count == 1
    assert bridge_report.workflow_report is None
    assert bridge_report.reason_codes == ["profile_output_parse_failed"]
    assert "not json" in bridge_report.stdout_redacted


class SequencedProfileRunner:
    def __init__(self, responses: list[tuple[str, str]]) -> None:
        self.responses = list(responses)
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        if not self.responses:
            return ProfileRunResult(stdout="", stderr="unexpected extra call", exit_code=127)
        expected_profile, stdout = self.responses.pop(0)
        if request.profile != expected_profile:
            return ProfileRunResult(stdout="", stderr=f"expected {expected_profile}, got {request.profile}", exit_code=126)
        return ProfileRunResult(stdout=stdout, stderr="", exit_code=0)


def test_real_profile_workflow_runner_productizes_worker_teacher_retry_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="w42d-productized-teacher-retry",
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Call teacher once after verifier failure, then retry worker once.",
    )
    profile_runner = SequencedProfileRunner(
        [
            ("weak", json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a * b\n"}]})),
            ("teacher", json.dumps({"guidance": "Use addition exactly: return a + b."})),
            ("weak", json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]})),
        ]
    )

    report = RealProfileWorkflowRunner(profile_runner=profile_runner).run(
        source_repo=repo,
        contract=contract,
        project_name="toy-calculator",
        worker_profile="weak",
        teacher_profile="teacher",
        authorization=RealProfileWorkflowAuthorization(
            scopes=["real_profile_workflow_execute", "teacher_escalation"],
            max_profile_calls=3,
            dry_run_only=True,
        ),
        evidence_root=tmp_path,
        run_id="w42d-productized-teacher-retry",
    )

    assert report.status == RealProfileWorkflowStatus.VERIFIED
    assert report.provider_call_count == 3
    assert report.teacher_profile == "teacher"
    assert report.workflow_report is not None
    assert report.workflow_report.verification_passed is True
    assert report.workflow_report.retry_performed is True
    assert len(report.workflow_report.teacher_guidance_events) == 1
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.source_repo_clean is True
    assert [request.role for request in profile_runner.requests] == ["worker", "teacher", "worker"]
    evidence_path = tmp_path / ".hermes" / "workflow-smokes" / "w42d-productized-teacher-retry" / "evidence.json"
    assert evidence_path.exists()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["status"] == "verified"
    assert payload["provider_call_count"] == 3
    assert payload["dry_run_only"] is True
    assert payload["promotion_attempted"] is False
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"


def test_real_project_dry_run_blocks_promotion_even_when_verified(tmp_path: Path) -> None:
    repo = tmp_path / "real-project"
    _init_toy_repo(repo)
    contract = TaskContract(
        task_id="w43a-real-project-dry-run",
        title="Dry-run calculator fix",
        scope="Verify a real-project-style dry run without promotion.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
        escalation_rule="Dry-run only; do not promote even if verified.",
    )
    profile_runner = FakeProfileRunner(
        {"weak": json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]})}
    )

    report = RealProfileWorkflowRunner(profile_runner=profile_runner).run(
        source_repo=repo,
        contract=contract,
        project_name="real-project-dry-run",
        worker_profile="weak",
        teacher_profile=None,
        authorization=RealProfileWorkflowAuthorization(
            scopes=["real_profile_workflow_execute"],
            max_profile_calls=1,
            dry_run_only=True,
            allow_real_project=True,
        ),
        evidence_root=tmp_path,
        run_id="w43a-real-project-dry-run",
    )

    assert report.status == RealProfileWorkflowStatus.VERIFIED
    assert report.workflow_report is not None
    assert report.workflow_report.promotion_ready is True
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.reason_codes == ["real_profile_workflow_execute_authorized", "dry_run_no_promotion"]
    assert report.source_repo_clean is True
    assert (repo / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
