from __future__ import annotations

import subprocess
from pathlib import Path

from feiyue_core.safety import HumanApprovalRecord
from feiyue_core.workflow import TaskContract
from feiyue_core.workflow.execution import (
    CandidateFileWrite,
    ProductionPromotionRequest,
    PromotionStatus,
    ToyWorkflowExecutor,
    WorkflowReportWriter,
)


def _init_toy_repo(path: Path) -> None:
    path.mkdir()
    (path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["."]\n', encoding="utf-8")
    (path / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (path / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_adds_numbers():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)


def _contract(task_id: str) -> TaskContract:
    return TaskContract(
        task_id=task_id,
        title="Fix calculator add",
        scope="Make add return a sum.",
        files_to_modify=["calc.py"],
        verification_commands=["python -m pytest -q"],
    )


def _approval(task_id: str, target_branch: str, *, action: str | None = None) -> HumanApprovalRecord:
    return HumanApprovalRecord(
        approval_id=f"approval-{task_id}",
        task_id=task_id,
        approved_action=action or f"production_promotion:{target_branch}",
        approver="human-reviewer",
        approved_at="2026-06-13T12:00:00Z",
        reason="Approve this exact production promotion boundary.",
    )


def _verified_report(repo: Path, task_id: str, writes: list[CandidateFileWrite]):
    executor = ToyWorkflowExecutor()
    return executor, executor.execute(
        source_repo=repo,
        contract=_contract(task_id),
        candidate_writes=writes,
        project_name="toy-calculator",
    )


def _production_request(
    task_id: str,
    target_branch: str,
    *,
    approval: HumanApprovalRecord | None = None,
    rollback_plan: str = "Reset target branch to rollback_ref if post-promotion verification fails.",
    allowed: list[str] | None = None,
) -> ProductionPromotionRequest:
    return ProductionPromotionRequest(
        task_id=task_id,
        target_branch=target_branch,
        allowed_target_branches=allowed or [target_branch],
        approval_record=approval,
        rollback_plan=rollback_plan,
    )


def test_production_promotion_blocks_unverified_report_with_safety_reason(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a * b\n")]
    executor = ToyWorkflowExecutor()
    report = executor.execute(source_repo=repo, contract=_contract("w3-unverified"), candidate_writes=writes, project_name="toy")

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="production/main",
        commit_message="feat: should not promote",
        production_request=_production_request(
            "w3-unverified", "production/main", approval=_approval("w3-unverified", "production/main")
        ),
    )

    assert promotion.status == PromotionStatus.BLOCKED
    assert promotion.safety_report is not None
    assert "report_not_promotion_ready" in promotion.safety_report.reasons
    assert promotion.side_effect_performed is False
    assert subprocess.run(["git", "branch", "--list", "production/main"], cwd=repo, text=True, capture_output=True, check=True).stdout.strip() == ""


def test_production_promotion_blocks_missing_human_approval(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor, report = _verified_report(repo, "w3-missing-approval", writes)

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="production/main",
        commit_message="feat: should not promote",
        production_request=_production_request("w3-missing-approval", "production/main"),
    )

    assert promotion.status == PromotionStatus.BLOCKED
    assert promotion.safety_report is not None
    assert "missing_or_mismatched_human_approval" in promotion.safety_report.reasons
    assert promotion.safety_report.approval_applies is False


def test_production_promotion_blocks_target_branch_mismatch(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor, report = _verified_report(repo, "w3-branch-mismatch", writes)

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="production/other",
        commit_message="feat: should not promote",
        production_request=_production_request(
            "w3-branch-mismatch", "production/main", approval=_approval("w3-branch-mismatch", "production/main")
        ),
    )

    assert promotion.status == PromotionStatus.BLOCKED
    assert promotion.safety_report is not None
    assert "target_branch_mismatch" in promotion.safety_report.reasons
    assert "target_branch_not_allowed" in promotion.safety_report.reasons


def test_production_promotion_blocks_dirty_source_repo(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor, report = _verified_report(repo, "w3-dirty-source", writes)
    (repo / "scratch.txt").write_text("dirty\n", encoding="utf-8")

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="production/main",
        commit_message="feat: should not promote",
        production_request=_production_request(
            "w3-dirty-source", "production/main", approval=_approval("w3-dirty-source", "production/main")
        ),
    )

    assert promotion.status == PromotionStatus.BLOCKED
    assert promotion.safety_report is not None
    assert "source_repo_dirty_before" in promotion.safety_report.reasons
    assert promotion.safety_report.source_repo_clean_before is False


def test_approved_verified_production_promotion_records_rollback_evidence_and_confirms_target_ref(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    base_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor, report = _verified_report(repo, "w3-approved", writes)

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="production/main",
        commit_message="feat: promote verified calculator fix",
        production_request=_production_request("w3-approved", "production/main", approval=_approval("w3-approved", "production/main")),
    )

    assert promotion.status == PromotionStatus.PROMOTED
    assert promotion.safety_report is not None
    assert promotion.safety_report.authorized is True
    assert promotion.safety_report.rollback_ref == base_sha
    assert promotion.rollback_ref == base_sha
    assert promotion.safety_report.target_ref_verified is True
    assert promotion.safety_report.promoted_ref == promotion.commit_sha
    assert promotion.safety_report.source_repo_clean_after is True
    artifacts = WorkflowReportWriter(repo).write(report=report, promotion=promotion)
    markdown = artifacts.promotion_markdown_path.read_text(encoding="utf-8")
    assert "## Rollback Plan" in markdown
    assert f"- rollback_ref: {base_sha}" in markdown
    assert "## Promotion Safety Report" in markdown
    assert "- target_ref_verified: True" in markdown


def test_simulated_production_promotion_failure_records_rollback_and_cleanup_state(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a - b\n")]
    executor, report = _verified_report(repo, "w3-failure", [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")])

    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch="production/failure",
        commit_message="feat: no-op should fail commit",
        production_request=_production_request("w3-failure", "production/failure", approval=_approval("w3-failure", "production/failure")),
    )

    assert promotion.status == PromotionStatus.FAILED
    assert promotion.safety_report is not None
    assert promotion.safety_report.rollback_ref is not None
    assert promotion.safety_report.rollback_plan_recorded is True
    assert promotion.promotion_worktree_removed is True
    assert promotion.safety_report.promotion_worktree_removed is True
    assert promotion.safety_report.source_repo_clean_after is True
    assert promotion.side_effect_performed is False
