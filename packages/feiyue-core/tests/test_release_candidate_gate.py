from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.promotion_lifecycle import DraftPRApproval, DraftPRStatus, compute_pr_plan_hash, create_approved_draft_pr, create_promotion_pr_plan
from feiyue_core.workflow.release_candidate import (
    MergeExecutionApproval,
    MergeExecutionAdapterResult,
    MergeRollbackDeployReadinessApproval,
    PRReadyForReviewAdapterResult,
    PRReadyForReviewApproval,
    PRReadyForReviewExternalMutationApproval,
    ProductionPromotionApproval,
    ReleaseCandidateStatus,
    approve_merge_execution,
    approve_merge_rollback_deploy_readiness,
    approve_pr_ready_for_review_external_mutation,
    approve_pr_ready_for_review_transition,
    approve_production_promotion,
    create_merge_rollback_deploy_readiness_plan,
    create_release_candidate_plan,
    execute_approved_merge,
    transition_pr_ready_for_review,
    verify_merge_rollback_deploy_readiness,
    verify_production_promotion_readiness,
)
from tests.test_draft_pr_mode import _cli_env
from tests.test_promotion_lifecycle import _git, _init_toy_repo, _promote_with_production_request


def _draft_pr_evidence(repo: Path, run_id: str = "run-rc", target_branch: str = "production/main") -> None:
    _promote_with_production_request(repo, run_id=run_id, target_branch=target_branch)
    plan = create_promotion_pr_plan(
        project_root=repo,
        run_id=run_id,
        allowed_target_branches=[target_branch],
        source_branch=f"candidate/{run_id}",
    )
    approval = DraftPRApproval(
        approval_id=f"approval-{run_id}",
        approved_by="human-reviewer",
        run_id=run_id,
        approved_action="create_draft_pr",
        plan_hash=compute_pr_plan_hash(plan),
        source_branch=f"candidate/{run_id}",
        target_branch=target_branch,
        rollback_ref=plan.rollback_ref or _git(repo, "rev-parse", "HEAD"),
        approved_at="2026-06-14T12:00:00Z",
        reason="Create fake draft PR evidence only.",
    )
    draft = create_approved_draft_pr(project_root=repo, run_id=run_id, approval=approval)
    assert draft.status == DraftPRStatus.CREATED


def _write_ci_success(repo: Path, name: str = "ci-success.json") -> Path:
    path = repo / ".hermes" / "ci" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "success", "run_url": "https://ci.example.invalid/runs/1"}), encoding="utf-8")
    return path


def _write_rollback_verified(repo: Path, run_id: str = "run-rc") -> Path:
    path = repo / ".hermes" / "promotion-lifecycle" / run_id / "rollback-evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "verified",
                "target_branch": "production/main",
                "sandbox_branch": f"hermes/rollback-sandbox/{run_id}",
                "rollback_ref": _git(repo, "rev-parse", "HEAD"),
                "verifier_command": "python -m pytest -q",
                "verifier_exit_code": 0,
                "reason_codes": [],
                "repo_clean_before": True,
                "repo_clean_after": True,
                "sandbox_worktree_removed": True,
                "external_side_effect_performed": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_release_candidate_plan_fails_closed_for_missing_ci(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _draft_pr_evidence(repo)
    rollback = _write_rollback_verified(repo)

    plan = create_release_candidate_plan(
        project_root=repo,
        release_id="wave5-6",
        run_id="run-rc",
        allowed_target_branches=["production/main"],
        ci_evidence_path=repo / ".hermes" / "ci" / "missing.json",
        rollback_evidence_path=rollback,
        post_promotion_verification_plan=["python -m pytest -q"],
    )

    assert plan.status == ReleaseCandidateStatus.BLOCKED
    assert "missing_ci_evidence" in plan.reason_codes
    assert plan.production_mutated is False


def test_release_candidate_plan_fails_closed_for_missing_rollback(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _draft_pr_evidence(repo)
    ci = _write_ci_success(repo)

    plan = create_release_candidate_plan(
        project_root=repo,
        release_id="wave5-6",
        run_id="run-rc",
        allowed_target_branches=["production/main"],
        ci_evidence_path=ci,
        rollback_evidence_path=repo / ".hermes" / "promotion-lifecycle" / "run-rc" / "missing-rollback.json",
        post_promotion_verification_plan=["python -m pytest -q"],
    )

    assert plan.status == ReleaseCandidateStatus.BLOCKED
    assert "missing_rollback_evidence" in plan.reason_codes
    assert plan.production_mutated is False


def test_production_promotion_readiness_fails_closed_for_wrong_approval_hash(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _draft_pr_evidence(repo)
    ci = _write_ci_success(repo)
    rollback = _write_rollback_verified(repo)
    create_release_candidate_plan(
        project_root=repo,
        release_id="wave5-6",
        run_id="run-rc",
        allowed_target_branches=["production/main"],
        ci_evidence_path=ci,
        rollback_evidence_path=rollback,
        post_promotion_verification_plan=["python -m pytest -q"],
    )
    bad_approval = ProductionPromotionApproval(
        approval_id="approval-prod-bad",
        approved_by="human-reviewer",
        release_id="wave5-6",
        run_id="run-rc",
        approved_action="promote_release_candidate_to_production",
        release_plan_hash="not-the-plan-hash",
        target_branch="production/main",
        approved_at="2026-06-14T12:00:00Z",
        reason="Bad hash should fail closed.",
    )

    readiness = verify_production_promotion_readiness(project_root=repo, release_id="wave5-6", approval=bad_approval)

    assert readiness.status == ReleaseCandidateStatus.BLOCKED
    assert "approval_release_plan_hash_mismatch" in readiness.reason_codes
    assert readiness.production_mutated is False
    assert readiness.dry_run is True


def test_release_candidate_dry_run_readiness_allowed_and_persisted(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _draft_pr_evidence(repo)
    ci = _write_ci_success(repo)
    rollback = _write_rollback_verified(repo)
    plan = create_release_candidate_plan(
        project_root=repo,
        release_id="wave5-6",
        run_id="run-rc",
        allowed_target_branches=["production/main"],
        ci_evidence_path=ci,
        rollback_evidence_path=rollback,
        post_promotion_verification_plan=["python -m pytest -q", "curl -fsS https://example.invalid/health || true"],
    )
    approval = approve_production_promotion(
        project_root=repo,
        release_id="wave5-6",
        approved_by="human-reviewer",
        approval_id="approval-prod",
        reason="Approve exact dry-run readiness only.",
    )

    readiness = verify_production_promotion_readiness(project_root=repo, release_id="wave5-6", approval=approval)

    assert plan.status == ReleaseCandidateStatus.PLANNED
    assert approval.release_plan_hash == plan.release_plan_hash
    assert readiness.status == ReleaseCandidateStatus.READY
    assert readiness.reason_codes == ["production_promotion_approval_applies", "dry_run_no_production_mutation"]
    assert readiness.production_mutated is False
    assert readiness.dry_run is True
    persisted = json.loads((repo / ".hermes" / "release-candidates" / "wave5-6" / "readiness.json").read_text(encoding="utf-8"))
    assert persisted["production_mutated"] is False


def test_release_candidate_cli_plan_approve_and_verify_fake_first(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _draft_pr_evidence(repo, run_id="run-cli-rc")
    ci = _write_ci_success(repo)
    rollback = _write_rollback_verified(repo, run_id="run-cli-rc")

    plan = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "release-candidate-plan",
            "wave5-6-cli",
            "--run-id",
            "run-cli-rc",
            "--allowed-target-branch",
            "production/main",
            "--ci-evidence-path",
            str(ci),
            "--rollback-evidence-path",
            str(rollback),
            "--post-promotion-verification-command",
            "python -m pytest -q",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    plan_payload = json.loads(plan.stdout)
    assert plan_payload["status"] == "planned"
    assert plan_payload["production_mutated"] is False

    approve = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "approve-production-promotion",
            "wave5-6-cli",
            "--approved-by",
            "human-reviewer",
            "--approval-id",
            "approval-cli-prod",
            "--reason",
            "Approve exact dry-run readiness only.",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    approval_payload = json.loads(approve.stdout)
    assert approval_payload["release_plan_hash"] == plan_payload["release_plan_hash"]

    readiness = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "verify-production-promotion-readiness",
            "wave5-6-cli",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    readiness_payload = json.loads(readiness.stdout)
    assert readiness_payload["status"] == "ready"
    assert readiness_payload["production_mutated"] is False


def _write_merge_readiness_evidence(repo: Path, *, readiness_id: str = "wave7-7d") -> Path:
    path = repo / ".hermes" / "merge-readiness" / readiness_id / "evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "readiness_id": readiness_id,
                "status": "ready_for_human_merge_review",
                "pr_number": 3,
                "pr_url": "https://github.com/sinonchum/Feiyue/pull/3",
                "source_branch": "feiyue/7b-real-feature-pr",
                "target_branch": "main",
                "head_sha": "abc123",
                "checks_passed": True,
                "is_draft": True,
                "auto_merge_request": None,
                "merge_performed": False,
                "auto_merge_enabled": False,
                "deploy_performed": False,
                "production_mutated": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_8a_merge_rollback_deploy_readiness_fails_closed_for_missing_exact_approval(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    evidence_path = _write_merge_readiness_evidence(repo)
    plan = create_merge_rollback_deploy_readiness_plan(
        project_root=repo,
        readiness_id="wave8-8a",
        merge_readiness_evidence_path=evidence_path,
        rollback_plan=["git revert <merge-sha>", "python -m pytest -q"],
        deploy_plan=["deploy smoke only after explicit deploy approval"],
        post_merge_verification_plan=["python -m pytest -q"],
    )

    readiness = verify_merge_rollback_deploy_readiness(project_root=repo, readiness_id="wave8-8a")

    assert plan.status == ReleaseCandidateStatus.PLANNED
    assert readiness.status == ReleaseCandidateStatus.BLOCKED
    assert "missing_merge_rollback_deploy_readiness_approval" in readiness.reason_codes
    assert readiness.merge_performed is False
    assert readiness.auto_merge_enabled is False
    assert readiness.deploy_performed is False
    assert readiness.production_mutated is False


def test_8a_merge_rollback_deploy_readiness_exact_approval_is_evidence_only(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    evidence_path = _write_merge_readiness_evidence(repo)
    plan = create_merge_rollback_deploy_readiness_plan(
        project_root=repo,
        readiness_id="wave8-8a",
        merge_readiness_evidence_path=evidence_path,
        rollback_plan=["git revert <merge-sha>", "python -m pytest -q"],
        deploy_plan=["deploy smoke only after explicit deploy approval"],
        post_merge_verification_plan=["python -m pytest -q"],
    )
    approval = approve_merge_rollback_deploy_readiness(
        project_root=repo,
        readiness_id="wave8-8a",
        approved_by="human-reviewer",
        approval_id="approval-8a",
        reason="Approve readiness design only; do not execute merge/deploy.",
    )

    readiness = verify_merge_rollback_deploy_readiness(project_root=repo, readiness_id="wave8-8a", approval=approval)

    assert approval.readiness_plan_hash == plan.readiness_plan_hash
    assert readiness.status == ReleaseCandidateStatus.READY
    assert readiness.approval_applies is True
    assert readiness.reason_codes == ["merge_rollback_deploy_readiness_approval_applies", "evidence_only_no_merge_deploy_mutation"]
    assert readiness.merge_performed is False
    assert readiness.auto_merge_enabled is False
    assert readiness.deploy_performed is False
    assert readiness.production_mutated is False
    persisted = json.loads((repo / ".hermes" / "merge-rollback-deploy-readiness" / "wave8-8a" / "readiness.json").read_text(encoding="utf-8"))
    assert persisted["production_mutated"] is False


def test_8a_cli_plan_approve_verify_is_evidence_only(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    evidence_path = _write_merge_readiness_evidence(repo, readiness_id="wave7-7d-cli")

    plan = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "merge-rollback-deploy-readiness-plan",
            "wave8-8a-cli",
            "--merge-readiness-evidence-path",
            str(evidence_path),
            "--rollback-command",
            "git revert <merge-sha>",
            "--deploy-step",
            "deploy smoke only after explicit deploy approval",
            "--post-merge-verification-command",
            "python -m pytest -q",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    plan_payload = json.loads(plan.stdout)
    assert plan_payload["status"] == "planned"
    assert plan_payload["merge_performed"] is False
    assert plan_payload["deploy_performed"] is False

    approval = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "approve-merge-rollback-deploy-readiness",
            "wave8-8a-cli",
            "--approved-by",
            "human-reviewer",
            "--approval-id",
            "approval-8a-cli",
            "--reason",
            "Approve readiness design only.",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    approval_payload = json.loads(approval.stdout)
    assert approval_payload["readiness_plan_hash"] == plan_payload["readiness_plan_hash"]

    readiness = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "verify-merge-rollback-deploy-readiness",
            "wave8-8a-cli",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    readiness_payload = json.loads(readiness.stdout)
    assert readiness_payload["status"] == "ready"
    assert readiness_payload["merge_performed"] is False
    assert readiness_payload["auto_merge_enabled"] is False
    assert readiness_payload["deploy_performed"] is False
    assert readiness_payload["production_mutated"] is False



def _write_8a_ready_evidence(repo: Path, *, readiness_id: str = "wave8-8a", is_draft: bool = False) -> None:
    evidence_path = _write_merge_readiness_evidence(repo, readiness_id="wave7-7d",)
    plan = create_merge_rollback_deploy_readiness_plan(
        project_root=repo,
        readiness_id=readiness_id,
        merge_readiness_evidence_path=evidence_path,
        rollback_plan=["git revert <merge-sha>", "python -m pytest -q"],
        deploy_plan=["deploy only after separate explicit deploy approval"],
        post_merge_verification_plan=["python -m pytest -q"],
    )
    if is_draft:
        # Preserve a draft PR signal in the underlying merge-readiness evidence for the 8B real-adapter gate.
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["is_draft"] = True
        evidence_path.write_text(json.dumps(payload), encoding="utf-8")
        plan = create_merge_rollback_deploy_readiness_plan(
            project_root=repo,
            readiness_id=readiness_id,
            merge_readiness_evidence_path=evidence_path,
            rollback_plan=["git revert <merge-sha>", "python -m pytest -q"],
            deploy_plan=["deploy only after separate explicit deploy approval"],
            post_merge_verification_plan=["python -m pytest -q"],
        )
    approval = approve_merge_rollback_deploy_readiness(
        project_root=repo,
        readiness_id=readiness_id,
        approved_by="human-reviewer",
        approval_id=f"approval-{readiness_id}",
        reason="Approve readiness design for 8B merge execution planning.",
    )
    readiness = verify_merge_rollback_deploy_readiness(project_root=repo, readiness_id=readiness_id, approval=approval)
    assert plan.status == ReleaseCandidateStatus.PLANNED
    assert readiness.status == ReleaseCandidateStatus.READY


def test_8b_merge_execution_fails_closed_without_exact_approval(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8a_ready_evidence(repo, readiness_id="wave8-8b")

    evidence = execute_approved_merge(project_root=repo, readiness_id="wave8-8b", approval=None)

    assert evidence.status == ReleaseCandidateStatus.BLOCKED
    assert "missing_merge_execution_approval" in evidence.reason_codes
    assert evidence.merge_performed is False
    assert evidence.external_side_effect_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False


def test_8b_fake_adapter_records_simulated_merge_without_external_side_effects(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8a_ready_evidence(repo, readiness_id="wave8-8b")
    approval = approve_merge_execution(
        project_root=repo,
        readiness_id="wave8-8b",
        approved_by="human-reviewer",
        approval_id="approval-8b",
        reason="Approve fake adapter merge execution smoke only.",
    )

    evidence = execute_approved_merge(project_root=repo, readiness_id="wave8-8b", approval=approval)

    assert isinstance(approval, MergeExecutionApproval)
    assert evidence.status == ReleaseCandidateStatus.READY
    assert evidence.approval_applies is True
    assert evidence.adapter == "fake"
    assert evidence.simulated_merge_performed is True
    assert evidence.merge_performed is False
    assert evidence.external_side_effect_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False
    assert evidence.reason_codes == ["merge_execution_approval_applies", "fake_adapter_simulated_merge_only"]
    assert (repo / ".hermes" / "merge-executions" / "wave8-8b" / "execution-fake.json").exists()


def test_8b_real_adapter_blocks_draft_pr_before_merge_side_effects(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8a_ready_evidence(repo, readiness_id="wave8-8b", is_draft=True)
    approval = approve_merge_execution(
        project_root=repo,
        readiness_id="wave8-8b",
        approved_by="human-reviewer",
        approval_id="approval-8b-real",
        reason="Approve real adapter only if PR is non-draft and mergeable.",
    )
    adapter_result = MergeExecutionAdapterResult(
        adapter="github",
        status=ReleaseCandidateStatus.BLOCKED,
        reason_codes=["pr_is_draft"],
        merge_performed=False,
        external_side_effect_performed=False,
    )

    evidence = execute_approved_merge(project_root=repo, readiness_id="wave8-8b", approval=approval, adapter_result=adapter_result)

    assert evidence.status == ReleaseCandidateStatus.BLOCKED
    assert "pr_is_draft" in evidence.reason_codes
    assert evidence.adapter == "github"
    assert evidence.merge_performed is False
    assert evidence.external_side_effect_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False
    assert (repo / ".hermes" / "merge-executions" / "wave8-8b" / "execution-github.json").exists()


def test_8b_cli_approve_and_fake_execute_merge_smoke(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8a_ready_evidence(repo, readiness_id="wave8-8b-cli")

    approval = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "approve-merge-execution",
            "wave8-8b-cli",
            "--approved-by",
            "human-reviewer",
            "--approval-id",
            "approval-8b-cli",
            "--reason",
            "Approve fake adapter merge execution smoke only.",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    approval_payload = json.loads(approval.stdout)
    assert approval_payload["approved_action"] == "execute_approved_merge"

    execution = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "execute-approved-merge",
            "wave8-8b-cli",
            "--adapter",
            "fake",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    execution_payload = json.loads(execution.stdout)
    assert execution_payload["status"] == "ready"
    assert execution_payload["simulated_merge_performed"] is True
    assert execution_payload["merge_performed"] is False
    assert execution_payload["external_side_effect_performed"] is False
    assert execution_payload["deploy_performed"] is False
    assert execution_payload["production_mutated"] is False



def _write_8b_fake_merge_execution(repo: Path, *, readiness_id: str = "wave8-8c") -> None:
    _write_8a_ready_evidence(repo, readiness_id=readiness_id, is_draft=True)
    approval = approve_merge_execution(
        project_root=repo,
        readiness_id=readiness_id,
        approved_by="human-reviewer",
        approval_id=f"approval-merge-{readiness_id}",
        reason="Approve fake merge execution prerequisite for 8C.",
    )
    evidence = execute_approved_merge(project_root=repo, readiness_id=readiness_id, approval=approval)
    assert evidence.status == ReleaseCandidateStatus.READY
    assert evidence.simulated_merge_performed is True


def test_8c_pr_ready_for_review_transition_fails_closed_without_exact_approval(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8b_fake_merge_execution(repo, readiness_id="wave8-8c")

    evidence = transition_pr_ready_for_review(project_root=repo, readiness_id="wave8-8c", approval=None)

    assert evidence.status == ReleaseCandidateStatus.BLOCKED
    assert "missing_pr_ready_for_review_approval" in evidence.reason_codes
    assert evidence.ready_for_review_performed is False
    assert evidence.external_side_effect_performed is False
    assert evidence.merge_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False


def test_8c_fake_adapter_simulates_ready_for_review_without_external_side_effects(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8b_fake_merge_execution(repo, readiness_id="wave8-8c")
    approval = approve_pr_ready_for_review_transition(
        project_root=repo,
        readiness_id="wave8-8c",
        approved_by="human-reviewer",
        approval_id="approval-8c",
        reason="Approve fake ready-for-review transition smoke only.",
    )

    evidence = transition_pr_ready_for_review(project_root=repo, readiness_id="wave8-8c", approval=approval)

    assert isinstance(approval, PRReadyForReviewApproval)
    assert evidence.status == ReleaseCandidateStatus.READY
    assert evidence.adapter == "fake"
    assert evidence.simulated_ready_for_review_performed is True
    assert evidence.ready_for_review_performed is False
    assert evidence.external_side_effect_performed is False
    assert evidence.merge_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False
    assert evidence.reason_codes == ["pr_ready_for_review_approval_applies", "fake_adapter_simulated_ready_for_review_only"]
    assert (repo / ".hermes" / "pr-ready-for-review" / "wave8-8c" / "transition-fake.json").exists()


def test_8c_github_adapter_blocks_without_external_pr_mutation_authorization(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8b_fake_merge_execution(repo, readiness_id="wave8-8c")
    approval = approve_pr_ready_for_review_transition(
        project_root=repo,
        readiness_id="wave8-8c",
        approved_by="human-reviewer",
        approval_id="approval-8c-github",
        reason="Approve only inspection unless external PR mutation is explicitly authorized.",
    )
    adapter_result = PRReadyForReviewAdapterResult(
        adapter="github",
        status=ReleaseCandidateStatus.BLOCKED,
        reason_codes=["external_pr_mutation_not_authorized"],
        ready_for_review_performed=False,
        external_side_effect_performed=False,
    )

    evidence = transition_pr_ready_for_review(project_root=repo, readiness_id="wave8-8c", approval=approval, adapter_result=adapter_result)

    assert evidence.status == ReleaseCandidateStatus.BLOCKED
    assert evidence.adapter == "github"
    assert "external_pr_mutation_not_authorized" in evidence.reason_codes
    assert evidence.ready_for_review_performed is False
    assert evidence.external_side_effect_performed is False
    assert evidence.merge_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False
    assert (repo / ".hermes" / "pr-ready-for-review" / "wave8-8c" / "transition-github.json").exists()


def test_8c_cli_approve_and_fake_ready_for_review_transition(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8b_fake_merge_execution(repo, readiness_id="wave8-8c-cli")

    approval = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "approve-pr-ready-for-review",
            "wave8-8c-cli",
            "--approved-by",
            "human-reviewer",
            "--approval-id",
            "approval-8c-cli",
            "--reason",
            "Approve fake ready-for-review transition smoke only.",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    approval_payload = json.loads(approval.stdout)
    assert approval_payload["approved_action"] == "transition_pr_ready_for_review"

    transition = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "transition-pr-ready-for-review",
            "wave8-8c-cli",
            "--adapter",
            "fake",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    payload = json.loads(transition.stdout)
    assert payload["status"] == "ready"
    assert payload["simulated_ready_for_review_performed"] is True
    assert payload["ready_for_review_performed"] is False
    assert payload["external_side_effect_performed"] is False
    assert payload["merge_performed"] is False
    assert payload["deploy_performed"] is False
    assert payload["production_mutated"] is False



def _write_8c_fake_ready_for_review(repo: Path, *, readiness_id: str = "wave8-8d") -> None:
    _write_8b_fake_merge_execution(repo, readiness_id=readiness_id)
    approval = approve_pr_ready_for_review_transition(
        project_root=repo,
        readiness_id=readiness_id,
        approved_by="human-reviewer",
        approval_id=f"approval-ready-{readiness_id}",
        reason="Approve fake ready-for-review prerequisite for 8D.",
    )
    evidence = transition_pr_ready_for_review(project_root=repo, readiness_id=readiness_id, approval=approval)
    assert evidence.status == ReleaseCandidateStatus.READY
    assert evidence.simulated_ready_for_review_performed is True


def test_8d_external_ready_for_review_requires_exact_external_mutation_approval(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8c_fake_ready_for_review(repo, readiness_id="wave8-8d")
    adapter_result = PRReadyForReviewAdapterResult(
        adapter="github",
        status=ReleaseCandidateStatus.READY,
        reason_codes=["github_pr_marked_ready_for_review"],
        ready_for_review_performed=True,
        external_side_effect_performed=True,
    )

    evidence = transition_pr_ready_for_review(project_root=repo, readiness_id="wave8-8d", adapter_result=adapter_result)

    assert evidence.status == ReleaseCandidateStatus.BLOCKED
    assert "missing_pr_ready_for_review_external_mutation_approval" in evidence.reason_codes
    assert evidence.ready_for_review_performed is False
    assert evidence.external_side_effect_performed is False
    assert evidence.merge_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False


def test_8d_exact_external_mutation_approval_allows_github_ready_for_review_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8c_fake_ready_for_review(repo, readiness_id="wave8-8d")
    approval = approve_pr_ready_for_review_external_mutation(
        project_root=repo,
        readiness_id="wave8-8d",
        approved_by="human-reviewer",
        approval_id="approval-8d",
        reason="Approve real GitHub Draft to Ready-for-review transition only; no merge, auto-merge, or deploy.",
    )
    adapter_result = PRReadyForReviewAdapterResult(
        adapter="github",
        status=ReleaseCandidateStatus.READY,
        reason_codes=["github_pr_marked_ready_for_review"],
        ready_for_review_performed=True,
        external_side_effect_performed=True,
    )

    evidence = transition_pr_ready_for_review(project_root=repo, readiness_id="wave8-8d", external_mutation_approval=approval, adapter_result=adapter_result)

    assert isinstance(approval, PRReadyForReviewExternalMutationApproval)
    assert evidence.status == ReleaseCandidateStatus.READY
    assert evidence.adapter == "github"
    assert evidence.ready_for_review_performed is True
    assert evidence.external_side_effect_performed is True
    assert evidence.merge_performed is False
    assert evidence.deploy_performed is False
    assert evidence.production_mutated is False
    assert evidence.reason_codes == ["pr_ready_for_review_external_mutation_approval_applies", "github_pr_marked_ready_for_review"]
    persisted = json.loads((repo / ".hermes" / "pr-ready-for-review" / "wave8-8d" / "transition-github.json").read_text(encoding="utf-8"))
    assert persisted["ready_for_review_performed"] is True
    assert persisted["merge_performed"] is False


def test_8d_cli_approves_external_pr_ready_for_review_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    _write_8c_fake_ready_for_review(repo, readiness_id="wave8-8d-cli")

    approval = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "approve-pr-ready-for-review-external-mutation",
            "wave8-8d-cli",
            "--approved-by",
            "human-reviewer",
            "--approval-id",
            "approval-8d-cli",
            "--reason",
            "Approve real GitHub Draft to Ready-for-review transition only.",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )

    payload = json.loads(approval.stdout)
    assert payload["approved_action"] == "perform_github_pr_ready_for_review"
    assert payload["ready_for_review_transition_hash"]
