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
    WorkflowExecutionStatus,
    ToyWorkflowExecutor,
    WorkflowReportWriter,
)


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
