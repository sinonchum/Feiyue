from __future__ import annotations

import json
import subprocess
from pathlib import Path

from feiyue_core.safety import HumanApprovalRecord
from feiyue_core.workflow import TaskContract
from feiyue_core.workflow.execution import CandidateFileWrite, ProductionPromotionRequest, ToyWorkflowExecutor
from feiyue_core.workflow.promotion_lifecycle import (
    PromotionLifecycleStatus,
    create_promotion_pr_plan,
    simulate_rollback_sandbox,
)
from feiyue_core.workflow.real_profile_promotion import (
    RealProfilePromotionApproval,
    RealProfilePromotionGate,
    compute_workflow_report_hash,
)
from feiyue_core.workflow.real_profile_workflow_runner import RealProfileWorkflowRunReport, RealProfileWorkflowStatus


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


def _init_toy_repo(path: Path) -> None:
    path.mkdir()
    (path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["."]\n', encoding="utf-8")
    (path / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (path / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_adds_numbers():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
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


def _human_approval(task_id: str, target_branch: str) -> HumanApprovalRecord:
    return HumanApprovalRecord(
        approval_id=f"human-{task_id}",
        task_id=task_id,
        approved_action=f"production_promotion:{target_branch}",
        approver="human-reviewer",
        approved_at="2026-06-13T12:00:00Z",
        reason="Approve promotion for lifecycle test.",
    )


def _real_profile_approval(repo: Path, run_report: RealProfileWorkflowRunReport, target_branch: str, writes: list[CandidateFileWrite]) -> RealProfilePromotionApproval:
    assert run_report.workflow_report is not None
    return RealProfilePromotionApproval(
        approval_id=f"approval-{run_report.run_id}",
        approved_by="human-reviewer",
        run_id=run_report.run_id,
        task_id=run_report.task_id,
        approved_action="promote_verified_dry_run",
        changed_files=[write.path for write in writes],
        target_branch=target_branch,
        source_commit_sha=_git(repo, "rev-parse", "HEAD"),
        workflow_report_hash=compute_workflow_report_hash(run_report.workflow_report),
        approved_at="2026-06-13T12:00:00Z",
        reason="Approve exact dry-run promotion.",
    )


def _promote_with_real_gate(repo: Path, run_id: str = "run-lifecycle", target_branch: str = "production/main") -> str:
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor()
    workflow_report = executor.execute(source_repo=repo, contract=_contract("task-lifecycle"), candidate_writes=writes, project_name="toy")
    assert workflow_report.verification_passed is True
    run_report = RealProfileWorkflowRunReport(
        run_id=run_id,
        task_id="task-lifecycle",
        status=RealProfileWorkflowStatus.VERIFIED,
        worker_profile="worker",
        provider_call_count=0,
        reason_codes=["verified"],
        dry_run_only=True,
        promotion_attempted=False,
        source_repo_clean=True,
        workflow_report=workflow_report,
    )
    result = RealProfilePromotionGate(workflow_executor=executor).promote_verified_dry_run(
        source_repo=repo,
        dry_run_report=run_report,
        candidate_writes=writes,
        target_branch=target_branch,
        commit_message="feat: promote verified calculator fix",
        approval=_real_profile_approval(repo, run_report, target_branch, writes),
        evidence_root=repo,
    )
    assert result.status == "promoted"
    subprocess.run(["git", "add", ".hermes/workflow-promotions"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "record promotion evidence"], cwd=repo, check=True)
    return run_id


def _promote_with_production_request(repo: Path, run_id: str = "run-prod", target_branch: str = "production/main") -> str:
    writes = [CandidateFileWrite(path="calc.py", content="def add(a, b):\n    return a + b\n")]
    executor = ToyWorkflowExecutor()
    report = executor.execute(source_repo=repo, contract=_contract(run_id), candidate_writes=writes, project_name="toy")
    promotion = executor.promote_verified_writes(
        source_repo=repo,
        report=report,
        candidate_writes=writes,
        target_branch=target_branch,
        commit_message="feat: promote verified calculator fix",
        production_request=ProductionPromotionRequest(
            task_id=run_id,
            target_branch=target_branch,
            allowed_target_branches=[target_branch],
            rollback_plan="Reset target branch to rollback_ref if verification fails.",
            approval_record=_human_approval(run_id, target_branch),
        ),
    )
    assert promotion.status == "promoted"
    evidence_dir = repo / ".hermes" / "workflow-promotions" / run_id
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "promotion-evidence.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": run_id,
                "status": "promoted",
                "target_branch": target_branch,
                "promotion_attempted": True,
                "promotion_result": promotion.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", ".hermes/workflow-promotions"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "record production promotion evidence"], cwd=repo, check=True)
    return run_id


def test_pr_plan_is_local_only_from_real_profile_promotion_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = _promote_with_real_gate(repo)

    plan = create_promotion_pr_plan(project_root=repo, run_id=run_id, allowed_target_branches=["production/main"])

    assert plan.status == PromotionLifecycleStatus.PLANNED
    assert plan.external_pr_created is False
    assert plan.target_branch == "production/main"
    assert plan.promoted_commit == _git(repo, "rev-parse", "production/main")
    assert "promotion_evidence" in plan.evidence_refs
    assert "no GitHub API call" in plan.body
    persisted = json.loads((repo / ".hermes" / "promotion-lifecycle" / run_id / "pr-plan.json").read_text(encoding="utf-8"))
    assert persisted["external_pr_created"] is False


def test_pr_plan_fails_closed_for_missing_promotion_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)

    plan = create_promotion_pr_plan(project_root=repo, run_id="missing-run", allowed_target_branches=["production/main"])

    assert plan.status == PromotionLifecycleStatus.BLOCKED
    assert "missing_promotion_evidence" in plan.reason_codes
    assert plan.external_pr_created is False


def test_pr_plan_fails_closed_for_non_allowlisted_branch(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = _promote_with_production_request(repo, run_id="run-branch", target_branch="production/main")

    plan = create_promotion_pr_plan(project_root=repo, run_id=run_id, allowed_target_branches=["production/release"])

    assert plan.status == PromotionLifecycleStatus.BLOCKED
    assert "target_branch_not_allowed" in plan.reason_codes


def test_rollback_sandbox_resets_local_branch_to_rollback_ref_and_runs_verifier(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    rollback_ref = _git(repo, "rev-parse", "HEAD")
    run_id = _promote_with_production_request(repo)

    evidence = simulate_rollback_sandbox(
        project_root=repo,
        run_id=run_id,
        allowed_target_branches=["production/main"],
        verifier_command="python -m pytest -q",
    )

    assert evidence.status == PromotionLifecycleStatus.FAILED
    assert evidence.rollback_ref == rollback_ref
    assert evidence.verifier_exit_code != 0
    assert "verifier_failed" in evidence.reason_codes
    assert evidence.external_side_effect_performed is False
    assert evidence.sandbox_worktree_removed is True
    assert _git(repo, "rev-parse", f"hermes/rollback-sandbox/{run_id}") == rollback_ref
    persisted = json.loads((repo / ".hermes" / "promotion-lifecycle" / run_id / "rollback-evidence.json").read_text(encoding="utf-8"))
    assert persisted["external_side_effect_performed"] is False


def test_rollback_sandbox_fails_closed_for_dirty_repo_and_missing_rollback_ref(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = "run-no-rollback"
    evidence_dir = repo / ".hermes" / "workflow-promotions" / run_id
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "promotion-evidence.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": "task-no-rollback",
                "status": "promoted",
                "target_branch": "production/main",
                "promotion_result": {"commit_sha": _git(repo, "rev-parse", "HEAD"), "target_branch": "production/main"},
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", ".hermes/workflow-promotions"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "record incomplete promotion evidence"], cwd=repo, check=True)
    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    evidence = simulate_rollback_sandbox(
        project_root=repo,
        run_id=run_id,
        allowed_target_branches=["production/main"],
        verifier_command="python -m pytest -q",
    )

    assert evidence.status == PromotionLifecycleStatus.BLOCKED
    assert "source_repo_dirty_before" in evidence.reason_codes
    assert "missing_rollback_ref" in evidence.reason_codes
    assert evidence.verifier_exit_code is None
