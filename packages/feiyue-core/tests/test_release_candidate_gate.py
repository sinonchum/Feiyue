from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.promotion_lifecycle import DraftPRApproval, DraftPRStatus, compute_pr_plan_hash, create_approved_draft_pr, create_promotion_pr_plan
from feiyue_core.workflow.release_candidate import (
    ProductionPromotionApproval,
    ReleaseCandidateStatus,
    approve_production_promotion,
    create_release_candidate_plan,
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
