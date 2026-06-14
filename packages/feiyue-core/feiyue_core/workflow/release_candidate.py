from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Mapping

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.promotion_lifecycle import PromotionLifecycleStatus


class ReleaseCandidateStatus(StrEnum):
    PLANNED = "planned"
    READY = "ready"
    BLOCKED = "blocked"


class RefreshedMergeReadinessEvidence(FeiyueModel):
    """Evidence-only refreshed merge readiness after PR ready-for-review transition."""

    refresh_id: str
    status: str
    pr_number: int
    pr_url: str
    source_branch: str
    target_branch: str
    head_sha: str | None = None
    is_draft: bool
    pr_state: str
    merge_state_status: str | None = None
    auto_merge_request: object | None = None
    checks: list[dict[str, object]] = Field(default_factory=list)
    checks_passed: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    merge_performed: bool = False
    auto_merge_enabled: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    written_at: str | None = None


class PreMergeFinalAudit(FeiyueModel):
    """8F-1 final audit artifact before asking for explicit real merge approval."""

    audit_id: str
    status: str
    refreshed_readiness_id: str
    refreshed_readiness_hash: str
    pr_number: int
    pr_url: str
    source_branch: str
    target_branch: str
    head_sha: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    checks: list[dict[str, object]] = Field(default_factory=list)
    checks_passed: bool = False
    merge_state_status: str | None = None
    auto_merge_request: object | None = None
    merge_approval_request_ready: bool = False
    approved_action_to_request: str = "execute_real_github_merge"
    reason_codes: list[str] = Field(default_factory=list)
    merge_performed: bool = False
    auto_merge_enabled: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    written_at: str | None = None


class ReleaseCandidatePlan(FeiyueModel):
    """Fail-closed, local-only release-candidate evidence bundle."""

    release_id: str
    run_id: str
    status: ReleaseCandidateStatus
    target_branch: str | None = None
    source_branch: str | None = None
    evidence_kind: str | None = None
    ci_evidence_path: str | None = None
    rollback_evidence_path: str | None = None
    post_promotion_verification_plan: list[str] = Field(default_factory=list)
    evidence_refs: dict[str, str] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    branch_allowed: bool = False
    ci_success: bool = False
    rollback_verified: bool = False
    dry_run: bool = True
    production_mutated: bool = False
    release_plan_hash: str | None = None
    written_at: str | None = None


class MergeRollbackDeployReadinessPlan(FeiyueModel):
    """Explicit merge/rollback/deploy readiness design; evidence only."""

    readiness_id: str
    status: ReleaseCandidateStatus
    merge_readiness_evidence_path: str
    pr_number: int | None = None
    pr_url: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    head_sha: str | None = None
    checks_passed: bool = False
    rollback_plan: list[str] = Field(default_factory=list)
    deploy_plan: list[str] = Field(default_factory=list)
    post_merge_verification_plan: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    merge_performed: bool = False
    auto_merge_enabled: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    readiness_plan_hash: str | None = None
    written_at: str | None = None


class MergeRollbackDeployReadinessApproval(FeiyueModel):
    """Exact human approval for readiness design only; no execution."""

    approval_id: str
    approved_by: str
    readiness_id: str
    approved_action: str
    readiness_plan_hash: str
    pr_number: int
    target_branch: str
    approved_at: str
    reason: str

    @field_validator(
        "approval_id",
        "approved_by",
        "readiness_id",
        "approved_action",
        "readiness_plan_hash",
        "target_branch",
        "approved_at",
        "reason",
    )
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class MergeRollbackDeployReadinessEvidence(FeiyueModel):
    readiness_id: str
    status: ReleaseCandidateStatus
    pr_number: int | None = None
    pr_url: str | None = None
    target_branch: str | None = None
    readiness_plan_hash: str | None = None
    approval_id: str | None = None
    approval_applies: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    deploy_plan: list[str] = Field(default_factory=list)
    post_merge_verification_plan: list[str] = Field(default_factory=list)
    merge_performed: bool = False
    auto_merge_enabled: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    written_at: str | None = None


class MergeExecutionApproval(FeiyueModel):
    """Exact approval for 8B merge execution; adapters still enforce fail-closed safety."""

    approval_id: str
    approved_by: str
    readiness_id: str
    approved_action: str
    readiness_plan_hash: str
    pr_number: int
    target_branch: str
    approved_at: str
    reason: str

    @field_validator(
        "approval_id",
        "approved_by",
        "readiness_id",
        "approved_action",
        "readiness_plan_hash",
        "target_branch",
        "approved_at",
        "reason",
    )
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class MergeExecutionAdapterResult(FeiyueModel):
    adapter: str
    status: ReleaseCandidateStatus
    reason_codes: list[str] = Field(default_factory=list)
    merge_performed: bool = False
    external_side_effect_performed: bool = False
    merge_commit_sha: str | None = None
    pr_url: str | None = None


class MergeExecutionEvidence(FeiyueModel):
    readiness_id: str
    status: ReleaseCandidateStatus
    pr_number: int | None = None
    pr_url: str | None = None
    target_branch: str | None = None
    readiness_plan_hash: str | None = None
    approval_id: str | None = None
    approval_applies: bool = False
    adapter: str = "fake"
    simulated_merge_performed: bool = False
    merge_performed: bool = False
    external_side_effect_performed: bool = False
    merge_commit_sha: str | None = None
    deploy_performed: bool = False
    production_mutated: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    post_merge_verification_plan: list[str] = Field(default_factory=list)
    written_at: str | None = None


class PRReadyForReviewApproval(FeiyueModel):
    """Exact approval for 8C PR ready-for-review transition."""

    approval_id: str
    approved_by: str
    readiness_id: str
    approved_action: str
    merge_execution_hash: str
    pr_number: int
    target_branch: str
    approved_at: str
    reason: str

    @field_validator(
        "approval_id",
        "approved_by",
        "readiness_id",
        "approved_action",
        "merge_execution_hash",
        "target_branch",
        "approved_at",
        "reason",
    )
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class PRReadyForReviewAdapterResult(FeiyueModel):
    adapter: str
    status: ReleaseCandidateStatus
    reason_codes: list[str] = Field(default_factory=list)
    ready_for_review_performed: bool = False
    external_side_effect_performed: bool = False
    pr_url: str | None = None


class PRReadyForReviewExternalMutationApproval(FeiyueModel):
    """Exact approval for the real GitHub Draft -> Ready-for-review mutation only."""

    approval_id: str
    approved_by: str
    readiness_id: str
    approved_action: str
    ready_for_review_transition_hash: str
    pr_number: int
    target_branch: str
    approved_at: str
    reason: str

    @field_validator(
        "approval_id",
        "approved_by",
        "readiness_id",
        "approved_action",
        "ready_for_review_transition_hash",
        "target_branch",
        "approved_at",
        "reason",
    )
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class PRReadyForReviewEvidence(FeiyueModel):
    readiness_id: str
    status: ReleaseCandidateStatus
    pr_number: int | None = None
    pr_url: str | None = None
    target_branch: str | None = None
    merge_execution_hash: str | None = None
    approval_id: str | None = None
    approval_applies: bool = False
    adapter: str = "fake"
    simulated_ready_for_review_performed: bool = False
    ready_for_review_performed: bool = False
    external_side_effect_performed: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    written_at: str | None = None


class ProductionPromotionApproval(FeiyueModel):
    """Exact human approval for production-promotion readiness only."""

    approval_id: str
    approved_by: str
    release_id: str
    run_id: str
    approved_action: str
    release_plan_hash: str
    target_branch: str
    approved_at: str
    reason: str

    @field_validator(
        "approval_id",
        "approved_by",
        "release_id",
        "run_id",
        "approved_action",
        "release_plan_hash",
        "target_branch",
        "approved_at",
        "reason",
    )
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class ProductionPromotionReadiness(FeiyueModel):
    release_id: str
    run_id: str | None = None
    status: ReleaseCandidateStatus
    target_branch: str | None = None
    release_plan_hash: str | None = None
    approval_id: str | None = None
    approval_applies: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    post_promotion_verification_plan: list[str] = Field(default_factory=list)
    dry_run: bool = True
    production_mutated: bool = False
    written_at: str | None = None


def merge_rollback_deploy_readiness_dir(project_root: str | Path, readiness_id: str) -> Path:
    return Path(project_root) / ".hermes" / "merge-rollback-deploy-readiness" / readiness_id


def merge_execution_dir(project_root: str | Path, readiness_id: str) -> Path:
    return Path(project_root) / ".hermes" / "merge-executions" / readiness_id


def pr_ready_for_review_dir(project_root: str | Path, readiness_id: str) -> Path:
    return Path(project_root) / ".hermes" / "pr-ready-for-review" / readiness_id


def merge_readiness_dir(project_root: str | Path, refresh_id: str) -> Path:
    return Path(project_root) / ".hermes" / "merge-readiness" / refresh_id


def pre_merge_audit_dir(project_root: str | Path, audit_id: str) -> Path:
    return Path(project_root) / ".hermes" / "pre-merge-audits" / audit_id


def compute_refreshed_merge_readiness_hash(evidence: RefreshedMergeReadinessEvidence) -> str:
    payload = evidence.model_dump(mode="json")
    payload["written_at"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_pre_merge_final_audit(
    *,
    project_root: str | Path,
    audit_id: str,
    refreshed_readiness: RefreshedMergeReadinessEvidence,
    current_head_sha: str | None,
    changed_files: list[str],
    checks: list[dict[str, object]],
) -> PreMergeFinalAudit:
    reasons: list[str] = []
    checks_passed = bool(checks) and all(_check_passed(check) for check in checks)
    if refreshed_readiness.status != "ready_for_human_merge_review":
        reasons.append("refreshed_merge_readiness_not_ready")
    if refreshed_readiness.is_draft:
        reasons.append("pr_is_draft")
    if refreshed_readiness.auto_merge_request is not None:
        reasons.append("auto_merge_already_enabled")
    if refreshed_readiness.merge_performed:
        reasons.append("readiness_indicates_merge_performed")
    if refreshed_readiness.deploy_performed:
        reasons.append("readiness_indicates_deploy_performed")
    if refreshed_readiness.production_mutated:
        reasons.append("readiness_indicates_production_mutation")
    if refreshed_readiness.head_sha and current_head_sha and refreshed_readiness.head_sha != current_head_sha:
        reasons.append("head_sha_drift")
    if not checks_passed or not refreshed_readiness.checks_passed:
        reasons.append("pr_checks_not_passed")
    if not changed_files:
        reasons.append("changed_files_empty")
    status = "blocked" if reasons else "approval_requested"
    audit = PreMergeFinalAudit(
        audit_id=audit_id,
        status=status,
        refreshed_readiness_id=refreshed_readiness.refresh_id,
        refreshed_readiness_hash=compute_refreshed_merge_readiness_hash(refreshed_readiness),
        pr_number=refreshed_readiness.pr_number,
        pr_url=refreshed_readiness.pr_url,
        source_branch=refreshed_readiness.source_branch,
        target_branch=refreshed_readiness.target_branch,
        head_sha=current_head_sha or refreshed_readiness.head_sha,
        changed_files=changed_files,
        checks=checks,
        checks_passed=checks_passed,
        merge_state_status=refreshed_readiness.merge_state_status,
        auto_merge_request=refreshed_readiness.auto_merge_request,
        merge_approval_request_ready=status == "approval_requested",
        approved_action_to_request="execute_real_github_merge",
        reason_codes=reasons if reasons else ["pre_merge_final_audit_passed_approval_request_ready", "evidence_only_no_merge_deploy_mutation"],
        merge_performed=False,
        auto_merge_enabled=False,
        deploy_performed=False,
        production_mutated=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    _write_json(pre_merge_audit_dir(project_root, audit_id) / "audit.json", audit.model_dump(mode="json"))
    return audit


def refresh_merge_readiness_after_ready_for_review(
    *,
    project_root: str | Path,
    refresh_id: str,
    pr_number: int,
    pr_url: str,
    source_branch: str,
    target_branch: str,
    head_sha: str | None,
    is_draft: bool,
    pr_state: str,
    merge_state_status: str | None,
    auto_merge_request: object | None,
    checks: list[dict[str, object]],
) -> RefreshedMergeReadinessEvidence:
    reasons: list[str] = []
    checks_passed = bool(checks) and all(_check_passed(check) for check in checks)
    if is_draft:
        reasons.append("pr_is_draft")
    if pr_state.upper() != "OPEN":
        reasons.append("pr_not_open")
    if merge_state_status and merge_state_status.upper() not in {"CLEAN", "HAS_HOOKS", "UNKNOWN"}:
        reasons.append("pr_not_mergeable")
    if auto_merge_request is not None:
        reasons.append("auto_merge_already_enabled")
    if not checks_passed:
        reasons.append("pr_checks_not_passed")
    status = "blocked" if reasons else "ready_for_human_merge_review"
    evidence = RefreshedMergeReadinessEvidence(
        refresh_id=refresh_id,
        status=status,
        pr_number=pr_number,
        pr_url=pr_url,
        source_branch=source_branch,
        target_branch=target_branch,
        head_sha=head_sha,
        is_draft=is_draft,
        pr_state=pr_state,
        merge_state_status=merge_state_status,
        auto_merge_request=auto_merge_request,
        checks=checks,
        checks_passed=checks_passed,
        reason_codes=reasons if reasons else ["pr_non_draft_checks_passed_merge_readiness_refreshed", "evidence_only_no_merge_deploy_mutation"],
        merge_performed=False,
        auto_merge_enabled=False,
        deploy_performed=False,
        production_mutated=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    _write_json(merge_readiness_dir(project_root, refresh_id) / "evidence.json", evidence.model_dump(mode="json"))
    return evidence


def create_merge_rollback_deploy_readiness_plan(
    *,
    project_root: str | Path,
    readiness_id: str,
    merge_readiness_evidence_path: str | Path,
    rollback_plan: list[str],
    deploy_plan: list[str],
    post_merge_verification_plan: list[str],
) -> MergeRollbackDeployReadinessPlan:
    root = Path(project_root)
    reasons: list[str] = []
    evidence_path = Path(merge_readiness_evidence_path)
    if not evidence_path.is_absolute():
        evidence_path = root / evidence_path

    evidence: dict[str, object] = {}
    if not evidence_path.exists():
        reasons.append("missing_merge_readiness_evidence")
    else:
        evidence = _read_json(evidence_path)
        if evidence.get("status") != "ready_for_human_merge_review":
            reasons.append("merge_readiness_not_ready_for_human_review")
        if evidence.get("checks_passed") is not True:
            reasons.append("pr_checks_not_passed")
        if evidence.get("merge_performed") is not False:
            reasons.append("merge_already_performed")
        if evidence.get("auto_merge_enabled") is not False:
            reasons.append("auto_merge_already_enabled")
        if evidence.get("deploy_performed") is not False:
            reasons.append("deploy_already_performed")
        if evidence.get("production_mutated") is not False:
            reasons.append("production_already_mutated")

    if not rollback_plan or any(not step.strip() for step in rollback_plan):
        reasons.append("missing_rollback_plan")
    if not deploy_plan or any(not step.strip() for step in deploy_plan):
        reasons.append("missing_deploy_plan")
    if not post_merge_verification_plan or any(not step.strip() for step in post_merge_verification_plan):
        reasons.append("missing_post_merge_verification_plan")

    status = ReleaseCandidateStatus.BLOCKED if reasons else ReleaseCandidateStatus.PLANNED
    plan = MergeRollbackDeployReadinessPlan(
        readiness_id=readiness_id,
        status=status,
        merge_readiness_evidence_path=_rel(root, evidence_path),
        pr_number=_int(evidence.get("pr_number")),
        pr_url=_str(evidence.get("pr_url")),
        source_branch=_str(evidence.get("source_branch")),
        target_branch=_str(evidence.get("target_branch")),
        head_sha=_str(evidence.get("head_sha")),
        checks_passed=evidence.get("checks_passed") is True,
        rollback_plan=rollback_plan,
        deploy_plan=deploy_plan,
        post_merge_verification_plan=post_merge_verification_plan,
        reason_codes=reasons,
        merge_performed=False,
        auto_merge_enabled=False,
        deploy_performed=False,
        production_mutated=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    plan.readiness_plan_hash = compute_merge_rollback_deploy_readiness_plan_hash(plan)
    _write_json(merge_rollback_deploy_readiness_dir(root, readiness_id) / "plan.json", plan.model_dump(mode="json"))
    return plan


def read_merge_rollback_deploy_readiness_plan(project_root: str | Path, readiness_id: str) -> MergeRollbackDeployReadinessPlan:
    path = merge_rollback_deploy_readiness_dir(project_root, readiness_id) / "plan.json"
    if not path.exists():
        raise FileNotFoundError(f"Merge/rollback/deploy readiness plan not found for readiness_id: {readiness_id}")
    return MergeRollbackDeployReadinessPlan.model_validate_json(path.read_text(encoding="utf-8"))


def compute_merge_rollback_deploy_readiness_plan_hash(plan: MergeRollbackDeployReadinessPlan) -> str:
    payload = plan.model_dump(mode="json")
    payload["written_at"] = None
    payload["readiness_plan_hash"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approve_merge_rollback_deploy_readiness(
    *,
    project_root: str | Path,
    readiness_id: str,
    approved_by: str,
    approval_id: str,
    reason: str,
) -> MergeRollbackDeployReadinessApproval:
    plan = read_merge_rollback_deploy_readiness_plan(project_root, readiness_id)
    plan_hash = plan.readiness_plan_hash or compute_merge_rollback_deploy_readiness_plan_hash(plan)
    approval = MergeRollbackDeployReadinessApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        readiness_id=readiness_id,
        approved_action="approve_merge_rollback_deploy_readiness_design_only",
        readiness_plan_hash=plan_hash,
        pr_number=plan.pr_number or 0,
        target_branch=plan.target_branch or "",
        approved_at=datetime.now(UTC).isoformat(),
        reason=reason,
    )
    _write_json(merge_rollback_deploy_readiness_dir(project_root, readiness_id) / "approval.json", approval.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()})
    return approval


def read_merge_rollback_deploy_readiness_approval(project_root: str | Path, readiness_id: str) -> MergeRollbackDeployReadinessApproval:
    path = merge_rollback_deploy_readiness_dir(project_root, readiness_id) / "approval.json"
    if not path.exists():
        raise FileNotFoundError(f"Merge/rollback/deploy readiness approval not found for readiness_id: {readiness_id}")
    payload = _read_json(path)
    payload.pop("written_at", None)
    return MergeRollbackDeployReadinessApproval.model_validate(payload)


def verify_merge_rollback_deploy_readiness(
    *,
    project_root: str | Path,
    readiness_id: str,
    approval: MergeRollbackDeployReadinessApproval | None = None,
) -> MergeRollbackDeployReadinessEvidence:
    root = Path(project_root)
    reasons: list[str] = []
    try:
        plan = read_merge_rollback_deploy_readiness_plan(root, readiness_id)
    except FileNotFoundError:
        plan = None
        reasons.append("missing_merge_rollback_deploy_readiness_plan")

    if approval is None:
        try:
            approval = read_merge_rollback_deploy_readiness_approval(root, readiness_id)
        except FileNotFoundError:
            reasons.append("missing_merge_rollback_deploy_readiness_approval")

    plan_hash = plan.readiness_plan_hash or compute_merge_rollback_deploy_readiness_plan_hash(plan) if plan is not None else None
    if plan is not None:
        if plan.status != ReleaseCandidateStatus.PLANNED:
            reasons.append("merge_rollback_deploy_readiness_plan_not_planned")
        if not plan.checks_passed:
            reasons.append("pr_checks_not_passed")
        if plan.merge_performed is not False:
            reasons.append("plan_indicates_merge_performed")
        if plan.auto_merge_enabled is not False:
            reasons.append("plan_indicates_auto_merge_enabled")
        if plan.deploy_performed is not False:
            reasons.append("plan_indicates_deploy_performed")
        if plan.production_mutated is not False:
            reasons.append("plan_indicates_production_mutation")
        if not plan.rollback_plan:
            reasons.append("missing_rollback_plan")
        if not plan.deploy_plan:
            reasons.append("missing_deploy_plan")
        if not plan.post_merge_verification_plan:
            reasons.append("missing_post_merge_verification_plan")

    if approval is not None and plan is not None:
        if approval.readiness_id != readiness_id:
            reasons.append("approval_readiness_id_mismatch")
        if approval.approved_action != "approve_merge_rollback_deploy_readiness_design_only":
            reasons.append("approval_action_mismatch")
        if approval.readiness_plan_hash != plan_hash:
            reasons.append("approval_readiness_plan_hash_mismatch")
        if approval.pr_number != (plan.pr_number or 0):
            reasons.append("approval_pr_number_mismatch")
        if approval.target_branch != (plan.target_branch or ""):
            reasons.append("approval_target_branch_mismatch")

    status = ReleaseCandidateStatus.BLOCKED if reasons else ReleaseCandidateStatus.READY
    evidence = MergeRollbackDeployReadinessEvidence(
        readiness_id=readiness_id,
        status=status,
        pr_number=plan.pr_number if plan is not None else None,
        pr_url=plan.pr_url if plan is not None else None,
        target_branch=plan.target_branch if plan is not None else None,
        readiness_plan_hash=plan_hash,
        approval_id=approval.approval_id if approval is not None else None,
        approval_applies=status == ReleaseCandidateStatus.READY,
        reason_codes=reasons if reasons else ["merge_rollback_deploy_readiness_approval_applies", "evidence_only_no_merge_deploy_mutation"],
        rollback_plan=plan.rollback_plan if plan is not None else [],
        deploy_plan=plan.deploy_plan if plan is not None else [],
        post_merge_verification_plan=plan.post_merge_verification_plan if plan is not None else [],
        merge_performed=False,
        auto_merge_enabled=False,
        deploy_performed=False,
        production_mutated=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    _write_json(merge_rollback_deploy_readiness_dir(root, readiness_id) / "readiness.json", evidence.model_dump(mode="json"))
    return evidence


def approve_merge_execution(
    *,
    project_root: str | Path,
    readiness_id: str,
    approved_by: str,
    approval_id: str,
    reason: str,
) -> MergeExecutionApproval:
    plan = read_merge_rollback_deploy_readiness_plan(project_root, readiness_id)
    readiness_path = merge_rollback_deploy_readiness_dir(project_root, readiness_id) / "readiness.json"
    if not readiness_path.exists():
        raise FileNotFoundError(f"Merge/rollback/deploy readiness evidence not found for readiness_id: {readiness_id}")
    readiness = MergeRollbackDeployReadinessEvidence.model_validate_json(readiness_path.read_text(encoding="utf-8"))
    if readiness.status != ReleaseCandidateStatus.READY:
        raise ValueError(f"Merge execution approval requires ready readiness evidence, got: {readiness.status}")
    plan_hash = plan.readiness_plan_hash or compute_merge_rollback_deploy_readiness_plan_hash(plan)
    approval = MergeExecutionApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        readiness_id=readiness_id,
        approved_action="execute_approved_merge",
        readiness_plan_hash=plan_hash,
        pr_number=plan.pr_number or 0,
        target_branch=plan.target_branch or "",
        approved_at=datetime.now(UTC).isoformat(),
        reason=reason,
    )
    write_merge_execution_approval(project_root, approval)
    return approval


def write_merge_execution_approval(project_root: str | Path, approval: MergeExecutionApproval) -> Path:
    path = merge_execution_dir(project_root, approval.readiness_id) / "approval.json"
    _write_json(path, approval.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()})
    return path


def read_merge_execution_approval(project_root: str | Path, readiness_id: str) -> MergeExecutionApproval:
    path = merge_execution_dir(project_root, readiness_id) / "approval.json"
    if not path.exists():
        raise FileNotFoundError(f"Merge execution approval not found for readiness_id: {readiness_id}")
    payload = _read_json(path)
    payload.pop("written_at", None)
    return MergeExecutionApproval.model_validate(payload)


def execute_approved_merge(
    *,
    project_root: str | Path,
    readiness_id: str,
    approval: MergeExecutionApproval | None = None,
    adapter_result: MergeExecutionAdapterResult | None = None,
) -> MergeExecutionEvidence:
    root = Path(project_root)
    reasons: list[str] = []
    plan: MergeRollbackDeployReadinessPlan | None = None
    readiness: MergeRollbackDeployReadinessEvidence | None = None
    try:
        plan = read_merge_rollback_deploy_readiness_plan(root, readiness_id)
    except FileNotFoundError:
        reasons.append("missing_merge_rollback_deploy_readiness_plan")
    readiness_path = merge_rollback_deploy_readiness_dir(root, readiness_id) / "readiness.json"
    if readiness_path.exists():
        readiness = MergeRollbackDeployReadinessEvidence.model_validate_json(readiness_path.read_text(encoding="utf-8"))
    else:
        reasons.append("missing_merge_rollback_deploy_readiness_evidence")

    if approval is None:
        try:
            approval = read_merge_execution_approval(root, readiness_id)
        except FileNotFoundError:
            reasons.append("missing_merge_execution_approval")

    plan_hash = plan.readiness_plan_hash or compute_merge_rollback_deploy_readiness_plan_hash(plan) if plan is not None else None
    if plan is not None:
        if plan.status != ReleaseCandidateStatus.PLANNED:
            reasons.append("merge_rollback_deploy_readiness_plan_not_planned")
        if plan.merge_performed is not False:
            reasons.append("plan_indicates_merge_performed")
        if plan.deploy_performed is not False:
            reasons.append("plan_indicates_deploy_performed")
        if plan.production_mutated is not False:
            reasons.append("plan_indicates_production_mutation")
    if readiness is not None:
        if readiness.status != ReleaseCandidateStatus.READY:
            reasons.append("merge_rollback_deploy_readiness_not_ready")
        if readiness.merge_performed is not False:
            reasons.append("readiness_indicates_merge_performed")
        if readiness.deploy_performed is not False:
            reasons.append("readiness_indicates_deploy_performed")
        if readiness.production_mutated is not False:
            reasons.append("readiness_indicates_production_mutation")

    if approval is not None and plan is not None:
        if approval.readiness_id != readiness_id:
            reasons.append("approval_readiness_id_mismatch")
        if approval.approved_action != "execute_approved_merge":
            reasons.append("approval_action_mismatch")
        if approval.readiness_plan_hash != plan_hash:
            reasons.append("approval_readiness_plan_hash_mismatch")
        if approval.pr_number != (plan.pr_number or 0):
            reasons.append("approval_pr_number_mismatch")
        if approval.target_branch != (plan.target_branch or ""):
            reasons.append("approval_target_branch_mismatch")

    if adapter_result is None:
        adapter_result = MergeExecutionAdapterResult(
            adapter="fake",
            status=ReleaseCandidateStatus.READY,
            reason_codes=["fake_adapter_simulated_merge_only"],
            merge_performed=False,
            external_side_effect_performed=False,
            pr_url=plan.pr_url if plan is not None else None,
        )

    if adapter_result.status != ReleaseCandidateStatus.READY:
        reasons.extend(adapter_result.reason_codes)
    if adapter_result.external_side_effect_performed and not adapter_result.merge_performed:
        reasons.append("adapter_external_side_effect_without_merge")

    status = ReleaseCandidateStatus.BLOCKED if reasons else ReleaseCandidateStatus.READY
    adapter = adapter_result.adapter
    evidence = MergeExecutionEvidence(
        readiness_id=readiness_id,
        status=status,
        pr_number=plan.pr_number if plan is not None else None,
        pr_url=adapter_result.pr_url or (plan.pr_url if plan is not None else None),
        target_branch=plan.target_branch if plan is not None else None,
        readiness_plan_hash=plan_hash,
        approval_id=approval.approval_id if approval is not None else None,
        approval_applies=status == ReleaseCandidateStatus.READY,
        adapter=adapter,
        simulated_merge_performed=status == ReleaseCandidateStatus.READY and adapter == "fake",
        merge_performed=status == ReleaseCandidateStatus.READY and adapter_result.merge_performed,
        external_side_effect_performed=status == ReleaseCandidateStatus.READY and adapter_result.external_side_effect_performed,
        merge_commit_sha=adapter_result.merge_commit_sha if status == ReleaseCandidateStatus.READY else None,
        deploy_performed=False,
        production_mutated=False,
        reason_codes=reasons if reasons else ["merge_execution_approval_applies", "fake_adapter_simulated_merge_only"] if adapter == "fake" else ["merge_execution_approval_applies"],
        rollback_plan=plan.rollback_plan if plan is not None else [],
        post_merge_verification_plan=plan.post_merge_verification_plan if plan is not None else [],
        written_at=datetime.now(UTC).isoformat(),
    )
    out_dir = merge_execution_dir(root, readiness_id)
    _write_json(out_dir / "execution.json", evidence.model_dump(mode="json"))
    _write_json(out_dir / f"execution-{adapter}.json", evidence.model_dump(mode="json"))
    return evidence


class GitHubMergeExecutionAdapter:
    """Fail-closed adapter shim for 8B; this class does not call GitHub merge APIs."""

    def inspect(self, *, plan: MergeRollbackDeployReadinessPlan) -> MergeExecutionAdapterResult:
        reasons: list[str] = []
        evidence_path = Path(plan.merge_readiness_evidence_path)
        if not evidence_path.is_absolute():
            evidence_path = Path.cwd() / evidence_path
        # The CLI passes project-local relative evidence; resolve from caller cwd only as a fallback.
        if evidence_path.exists():
            payload = _read_json(evidence_path)
            if payload.get("is_draft") is True:
                reasons.append("pr_is_draft")
            if payload.get("checks_passed") is not True:
                reasons.append("pr_checks_not_passed")
        else:
            reasons.append("missing_merge_readiness_evidence")
        if reasons:
            return MergeExecutionAdapterResult(adapter="github", status=ReleaseCandidateStatus.BLOCKED, reason_codes=reasons, merge_performed=False, external_side_effect_performed=False, pr_url=plan.pr_url)
        return MergeExecutionAdapterResult(
            adapter="github",
            status=ReleaseCandidateStatus.BLOCKED,
            reason_codes=["github_merge_adapter_requires_separate_explicit_merge_authorization"],
            merge_performed=False,
            external_side_effect_performed=False,
            pr_url=plan.pr_url,
        )


def compute_merge_execution_hash(evidence: MergeExecutionEvidence) -> str:
    payload = evidence.model_dump(mode="json")
    payload["written_at"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_merge_execution_evidence(project_root: str | Path, readiness_id: str, *, adapter: str = "fake") -> MergeExecutionEvidence:
    path = merge_execution_dir(project_root, readiness_id) / f"execution-{adapter}.json"
    if not path.exists():
        path = merge_execution_dir(project_root, readiness_id) / "execution.json"
    if not path.exists():
        raise FileNotFoundError(f"Merge execution evidence not found for readiness_id: {readiness_id}")
    return MergeExecutionEvidence.model_validate_json(path.read_text(encoding="utf-8"))


def approve_pr_ready_for_review_transition(
    *,
    project_root: str | Path,
    readiness_id: str,
    approved_by: str,
    approval_id: str,
    reason: str,
) -> PRReadyForReviewApproval:
    merge_execution = read_merge_execution_evidence(project_root, readiness_id, adapter="fake")
    if merge_execution.status != ReleaseCandidateStatus.READY:
        raise ValueError(f"PR ready-for-review approval requires ready merge execution evidence, got: {merge_execution.status}")
    if merge_execution.merge_performed is not False or merge_execution.external_side_effect_performed is not False:
        raise ValueError("PR ready-for-review approval requires no prior real merge or external side effect")
    execution_hash = compute_merge_execution_hash(merge_execution)
    approval = PRReadyForReviewApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        readiness_id=readiness_id,
        approved_action="transition_pr_ready_for_review",
        merge_execution_hash=execution_hash,
        pr_number=merge_execution.pr_number or 0,
        target_branch=merge_execution.target_branch or "",
        approved_at=datetime.now(UTC).isoformat(),
        reason=reason,
    )
    write_pr_ready_for_review_approval(project_root, approval)
    return approval


def write_pr_ready_for_review_approval(project_root: str | Path, approval: PRReadyForReviewApproval) -> Path:
    path = pr_ready_for_review_dir(project_root, approval.readiness_id) / "approval.json"
    _write_json(path, approval.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()})
    return path


def read_pr_ready_for_review_approval(project_root: str | Path, readiness_id: str) -> PRReadyForReviewApproval:
    path = pr_ready_for_review_dir(project_root, readiness_id) / "approval.json"
    if not path.exists():
        raise FileNotFoundError(f"PR ready-for-review approval not found for readiness_id: {readiness_id}")
    payload = _read_json(path)
    payload.pop("written_at", None)
    return PRReadyForReviewApproval.model_validate(payload)


def compute_pr_ready_for_review_transition_hash(evidence: PRReadyForReviewEvidence) -> str:
    payload = evidence.model_dump(mode="json")
    payload["written_at"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_pr_ready_for_review_evidence(project_root: str | Path, readiness_id: str, *, adapter: str = "fake") -> PRReadyForReviewEvidence:
    path = pr_ready_for_review_dir(project_root, readiness_id) / f"transition-{adapter}.json"
    if not path.exists():
        path = pr_ready_for_review_dir(project_root, readiness_id) / "transition.json"
    if not path.exists():
        raise FileNotFoundError(f"PR ready-for-review transition evidence not found for readiness_id: {readiness_id}")
    return PRReadyForReviewEvidence.model_validate_json(path.read_text(encoding="utf-8"))


def approve_pr_ready_for_review_external_mutation(
    *,
    project_root: str | Path,
    readiness_id: str,
    approved_by: str,
    approval_id: str,
    reason: str,
) -> PRReadyForReviewExternalMutationApproval:
    transition = read_pr_ready_for_review_evidence(project_root, readiness_id, adapter="fake")
    if transition.status != ReleaseCandidateStatus.READY:
        raise ValueError(f"External PR mutation approval requires ready fake transition evidence, got: {transition.status}")
    if transition.ready_for_review_performed is not False or transition.external_side_effect_performed is not False:
        raise ValueError("External PR mutation approval requires no prior real ready-for-review side effect")
    transition_hash = compute_pr_ready_for_review_transition_hash(transition)
    approval = PRReadyForReviewExternalMutationApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        readiness_id=readiness_id,
        approved_action="perform_github_pr_ready_for_review",
        ready_for_review_transition_hash=transition_hash,
        pr_number=transition.pr_number or 0,
        target_branch=transition.target_branch or "",
        approved_at=datetime.now(UTC).isoformat(),
        reason=reason,
    )
    write_pr_ready_for_review_external_mutation_approval(project_root, approval)
    return approval


def write_pr_ready_for_review_external_mutation_approval(project_root: str | Path, approval: PRReadyForReviewExternalMutationApproval) -> Path:
    path = pr_ready_for_review_dir(project_root, approval.readiness_id) / "external-mutation-approval.json"
    _write_json(path, approval.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()})
    return path


def read_pr_ready_for_review_external_mutation_approval(project_root: str | Path, readiness_id: str) -> PRReadyForReviewExternalMutationApproval:
    path = pr_ready_for_review_dir(project_root, readiness_id) / "external-mutation-approval.json"
    if not path.exists():
        raise FileNotFoundError(f"PR ready-for-review external mutation approval not found for readiness_id: {readiness_id}")
    payload = _read_json(path)
    payload.pop("written_at", None)
    return PRReadyForReviewExternalMutationApproval.model_validate(payload)


def transition_pr_ready_for_review(
    *,
    project_root: str | Path,
    readiness_id: str,
    approval: PRReadyForReviewApproval | None = None,
    adapter_result: PRReadyForReviewAdapterResult | None = None,
    external_mutation_approval: PRReadyForReviewExternalMutationApproval | None = None,
) -> PRReadyForReviewEvidence:
    root = Path(project_root)
    reasons: list[str] = []
    try:
        merge_execution = read_merge_execution_evidence(root, readiness_id, adapter="fake")
    except FileNotFoundError:
        merge_execution = None
        reasons.append("missing_merge_execution_evidence")

    if approval is None:
        try:
            approval = read_pr_ready_for_review_approval(root, readiness_id)
        except FileNotFoundError:
            reasons.append("missing_pr_ready_for_review_approval")

    execution_hash = compute_merge_execution_hash(merge_execution) if merge_execution is not None else None
    if merge_execution is not None:
        if merge_execution.status != ReleaseCandidateStatus.READY:
            reasons.append("merge_execution_not_ready")
        if merge_execution.merge_performed is not False:
            reasons.append("merge_execution_indicates_real_merge")
        if merge_execution.external_side_effect_performed is not False:
            reasons.append("merge_execution_indicates_external_side_effect")
        if merge_execution.deploy_performed is not False:
            reasons.append("merge_execution_indicates_deploy")
        if merge_execution.production_mutated is not False:
            reasons.append("merge_execution_indicates_production_mutation")

    if approval is not None and merge_execution is not None:
        if approval.readiness_id != readiness_id:
            reasons.append("approval_readiness_id_mismatch")
        if approval.approved_action != "transition_pr_ready_for_review":
            reasons.append("approval_action_mismatch")
        if approval.merge_execution_hash != execution_hash:
            reasons.append("approval_merge_execution_hash_mismatch")
        if approval.pr_number != (merge_execution.pr_number or 0):
            reasons.append("approval_pr_number_mismatch")
        if approval.target_branch != (merge_execution.target_branch or ""):
            reasons.append("approval_target_branch_mismatch")

    fake_transition_hash: str | None = None
    if adapter_result is not None and adapter_result.external_side_effect_performed:
        try:
            fake_transition = read_pr_ready_for_review_evidence(root, readiness_id, adapter="fake")
            fake_transition_hash = compute_pr_ready_for_review_transition_hash(fake_transition)
        except FileNotFoundError:
            reasons.append("missing_fake_pr_ready_for_review_transition_evidence")
        if external_mutation_approval is None:
            try:
                external_mutation_approval = read_pr_ready_for_review_external_mutation_approval(root, readiness_id)
            except FileNotFoundError:
                reasons.append("missing_pr_ready_for_review_external_mutation_approval")
        if external_mutation_approval is not None:
            if external_mutation_approval.readiness_id != readiness_id:
                reasons.append("external_approval_readiness_id_mismatch")
            if external_mutation_approval.approved_action != "perform_github_pr_ready_for_review":
                reasons.append("external_approval_action_mismatch")
            if fake_transition_hash is not None and external_mutation_approval.ready_for_review_transition_hash != fake_transition_hash:
                reasons.append("external_approval_transition_hash_mismatch")
            if merge_execution is not None and external_mutation_approval.pr_number != (merge_execution.pr_number or 0):
                reasons.append("external_approval_pr_number_mismatch")
            if merge_execution is not None and external_mutation_approval.target_branch != (merge_execution.target_branch or ""):
                reasons.append("external_approval_target_branch_mismatch")

    if adapter_result is None:
        adapter_result = PRReadyForReviewAdapterResult(
            adapter="fake",
            status=ReleaseCandidateStatus.READY,
            reason_codes=["fake_adapter_simulated_ready_for_review_only"],
            ready_for_review_performed=False,
            external_side_effect_performed=False,
            pr_url=merge_execution.pr_url if merge_execution is not None else None,
        )

    if adapter_result.status != ReleaseCandidateStatus.READY:
        reasons.extend(adapter_result.reason_codes)
    if adapter_result.external_side_effect_performed and not adapter_result.ready_for_review_performed:
        reasons.append("adapter_external_side_effect_without_ready_for_review")

    status = ReleaseCandidateStatus.BLOCKED if reasons else ReleaseCandidateStatus.READY
    adapter = adapter_result.adapter
    evidence = PRReadyForReviewEvidence(
        readiness_id=readiness_id,
        status=status,
        pr_number=merge_execution.pr_number if merge_execution is not None else None,
        pr_url=adapter_result.pr_url or (merge_execution.pr_url if merge_execution is not None else None),
        target_branch=merge_execution.target_branch if merge_execution is not None else None,
        merge_execution_hash=execution_hash,
        approval_id=approval.approval_id if approval is not None else None,
        approval_applies=status == ReleaseCandidateStatus.READY,
        adapter=adapter,
        simulated_ready_for_review_performed=status == ReleaseCandidateStatus.READY and adapter == "fake",
        ready_for_review_performed=status == ReleaseCandidateStatus.READY and adapter_result.ready_for_review_performed,
        external_side_effect_performed=status == ReleaseCandidateStatus.READY and adapter_result.external_side_effect_performed,
        merge_performed=False,
        deploy_performed=False,
        production_mutated=False,
        reason_codes=(
            reasons
            if reasons
            else ["pr_ready_for_review_approval_applies", "fake_adapter_simulated_ready_for_review_only"]
            if adapter == "fake"
            else ["pr_ready_for_review_external_mutation_approval_applies", *(adapter_result.reason_codes or [])]
        ),
        written_at=datetime.now(UTC).isoformat(),
    )
    out_dir = pr_ready_for_review_dir(root, readiness_id)
    _write_json(out_dir / "transition.json", evidence.model_dump(mode="json"))
    _write_json(out_dir / f"transition-{adapter}.json", evidence.model_dump(mode="json"))
    return evidence


class GitHubPRReadyForReviewAdapter:
    """8C/8D GitHub PR ready-for-review adapter."""

    def inspect(self, *, merge_execution: MergeExecutionEvidence) -> PRReadyForReviewAdapterResult:
        return PRReadyForReviewAdapterResult(
            adapter="github",
            status=ReleaseCandidateStatus.BLOCKED,
            reason_codes=["external_pr_mutation_not_authorized"],
            ready_for_review_performed=False,
            external_side_effect_performed=False,
            pr_url=merge_execution.pr_url,
        )

    def execute(self, *, project_root: str | Path, pr_number: int, pr_url: str | None = None) -> PRReadyForReviewAdapterResult:
        try:
            completed = subprocess.run(
                ["gh", "pr", "ready", str(pr_number)],
                cwd=str(project_root),
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
        except Exception as exc:  # pragma: no cover - defensive shell boundary
            return PRReadyForReviewAdapterResult(
                adapter="github",
                status=ReleaseCandidateStatus.BLOCKED,
                reason_codes=[f"github_pr_ready_command_failed:{type(exc).__name__}"],
                ready_for_review_performed=False,
                external_side_effect_performed=False,
                pr_url=pr_url,
            )
        if completed.returncode != 0:
            return PRReadyForReviewAdapterResult(
                adapter="github",
                status=ReleaseCandidateStatus.BLOCKED,
                reason_codes=["github_pr_ready_command_failed"],
                ready_for_review_performed=False,
                external_side_effect_performed=False,
                pr_url=pr_url,
            )
        return PRReadyForReviewAdapterResult(
            adapter="github",
            status=ReleaseCandidateStatus.READY,
            reason_codes=["github_pr_marked_ready_for_review"],
            ready_for_review_performed=True,
            external_side_effect_performed=True,
            pr_url=pr_url,
        )


def release_candidate_dir(project_root: str | Path, release_id: str) -> Path:
    return Path(project_root) / ".hermes" / "release-candidates" / release_id


def create_release_candidate_plan(
    *,
    project_root: str | Path,
    release_id: str,
    run_id: str,
    allowed_target_branches: list[str],
    ci_evidence_path: str | Path,
    rollback_evidence_path: str | Path | None = None,
    post_promotion_verification_plan: list[str] | None = None,
) -> ReleaseCandidatePlan:
    """Create local-only release-candidate plan; never mutates production.

    Required evidence is intentionally explicit and fail-closed:
    draft PR evidence or promoted branch evidence, successful CI evidence,
    allowlisted target branch, verified rollback evidence, and a non-empty
    post-promotion verification plan.
    """

    root = Path(project_root)
    reasons: list[str] = []
    evidence_refs: dict[str, str] = {}
    evidence_kind: str | None = None
    target_branch: str | None = None
    source_branch: str | None = None

    draft_path = root / ".hermes" / "promotion-lifecycle" / run_id / "draft-pr-evidence.json"
    promotion_path = root / ".hermes" / "workflow-promotions" / run_id / "promotion-evidence.json"
    if draft_path.exists():
        draft = _read_json(draft_path)
        evidence_refs["draft_pr_evidence"] = _rel(root, draft_path)
        evidence_kind = "draft_pr"
        target_branch = _str(draft.get("target_branch"))
        source_branch = _str(draft.get("source_branch"))
        if draft.get("status") != "created":
            reasons.append("draft_pr_not_created")
        if draft.get("mutates_production") is not False:
            reasons.append("draft_pr_mutates_production")
        if draft.get("external_pr_created") is not False:
            reasons.append("draft_pr_not_fake_first")
    elif promotion_path.exists():
        promotion = _read_json(promotion_path)
        evidence_refs["promotion_evidence"] = _rel(root, promotion_path)
        evidence_kind = "promoted_branch"
        target_branch = _target_branch(promotion)
        source_branch = _str(promotion.get("source_branch"))
        if promotion.get("status") != "promoted":
            reasons.append("promotion_not_promoted")
    else:
        reasons.append("missing_draft_pr_or_promoted_branch_evidence")

    branch_allowed = bool(target_branch and target_branch in allowed_target_branches)
    if not target_branch:
        reasons.append("missing_target_branch")
    elif not branch_allowed:
        reasons.append("target_branch_not_allowed")

    ci_path = Path(ci_evidence_path)
    if not ci_path.is_absolute():
        ci_path = root / ci_path
    ci_success = False
    if not ci_path.exists():
        reasons.append("missing_ci_evidence")
    else:
        evidence_refs["ci_evidence"] = _rel(root, ci_path)
        ci = _read_json(ci_path)
        ci_success = _ci_success(ci)
        if not ci_success:
            reasons.append("ci_not_successful")

    rollback_path = Path(rollback_evidence_path) if rollback_evidence_path is not None else root / ".hermes" / "promotion-lifecycle" / run_id / "rollback-evidence.json"
    if not rollback_path.is_absolute():
        rollback_path = root / rollback_path
    rollback_verified = False
    if not rollback_path.exists():
        reasons.append("missing_rollback_evidence")
    else:
        evidence_refs["rollback_evidence"] = _rel(root, rollback_path)
        rollback = _read_json(rollback_path)
        rollback_verified = rollback.get("status") == PromotionLifecycleStatus.VERIFIED.value or rollback.get("status") == "verified"
        if not rollback_verified:
            reasons.append("rollback_not_verified")
        if rollback.get("external_side_effect_performed") is not False:
            reasons.append("rollback_external_side_effect")
        rollback_target = _str(rollback.get("target_branch"))
        if target_branch and rollback_target and rollback_target != target_branch:
            reasons.append("rollback_target_branch_mismatch")

    verification_plan = post_promotion_verification_plan or []
    if not verification_plan or any(not command.strip() for command in verification_plan):
        reasons.append("missing_post_promotion_verification_plan")

    status = ReleaseCandidateStatus.BLOCKED if reasons else ReleaseCandidateStatus.PLANNED
    plan = ReleaseCandidatePlan(
        release_id=release_id,
        run_id=run_id,
        status=status,
        target_branch=target_branch,
        source_branch=source_branch,
        evidence_kind=evidence_kind,
        ci_evidence_path=_rel(root, ci_path) if ci_path.exists() else _rel(root, ci_path),
        rollback_evidence_path=_rel(root, rollback_path) if rollback_path.exists() else _rel(root, rollback_path),
        post_promotion_verification_plan=verification_plan,
        evidence_refs=evidence_refs,
        reason_codes=reasons,
        branch_allowed=branch_allowed,
        ci_success=ci_success,
        rollback_verified=rollback_verified,
        dry_run=True,
        production_mutated=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    plan.release_plan_hash = compute_release_candidate_plan_hash(plan)
    _write_json(release_candidate_dir(root, release_id) / "plan.json", plan.model_dump(mode="json"))
    return plan


def read_release_candidate_plan(project_root: str | Path, release_id: str) -> ReleaseCandidatePlan:
    path = release_candidate_dir(project_root, release_id) / "plan.json"
    if not path.exists():
        raise FileNotFoundError(f"Release candidate plan not found for release_id: {release_id}")
    return ReleaseCandidatePlan.model_validate_json(path.read_text(encoding="utf-8"))


def compute_release_candidate_plan_hash(plan: ReleaseCandidatePlan) -> str:
    payload = plan.model_dump(mode="json")
    payload["written_at"] = None
    payload["release_plan_hash"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approve_production_promotion(
    *,
    project_root: str | Path,
    release_id: str,
    approved_by: str,
    approval_id: str,
    reason: str,
) -> ProductionPromotionApproval:
    plan = read_release_candidate_plan(project_root, release_id)
    plan_hash = plan.release_plan_hash or compute_release_candidate_plan_hash(plan)
    approval = ProductionPromotionApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        release_id=release_id,
        run_id=plan.run_id,
        approved_action="promote_release_candidate_to_production",
        release_plan_hash=plan_hash,
        target_branch=plan.target_branch or "",
        approved_at=datetime.now(UTC).isoformat(),
        reason=reason,
    )
    write_production_promotion_approval(project_root, approval)
    return approval


def write_production_promotion_approval(project_root: str | Path, approval: ProductionPromotionApproval) -> Path:
    path = release_candidate_dir(project_root, approval.release_id) / "production-approval.json"
    _write_json(path, approval.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()})
    return path


def read_production_promotion_approval(project_root: str | Path, release_id: str) -> ProductionPromotionApproval:
    path = release_candidate_dir(project_root, release_id) / "production-approval.json"
    if not path.exists():
        raise FileNotFoundError(f"Production promotion approval not found for release_id: {release_id}")
    payload = _read_json(path)
    payload.pop("written_at", None)
    return ProductionPromotionApproval.model_validate(payload)


def verify_production_promotion_readiness(
    *,
    project_root: str | Path,
    release_id: str,
    approval: ProductionPromotionApproval | None = None,
) -> ProductionPromotionReadiness:
    root = Path(project_root)
    reasons: list[str] = []
    plan: ReleaseCandidatePlan | None = None
    try:
        plan = read_release_candidate_plan(root, release_id)
    except FileNotFoundError:
        reasons.append("missing_release_candidate_plan")

    if approval is None:
        try:
            approval = read_production_promotion_approval(root, release_id)
        except FileNotFoundError:
            reasons.append("missing_production_promotion_approval")

    plan_hash = plan.release_plan_hash or compute_release_candidate_plan_hash(plan) if plan is not None else None
    if plan is not None:
        if plan.status != ReleaseCandidateStatus.PLANNED:
            reasons.append("release_candidate_plan_not_planned")
        if plan.production_mutated is not False:
            reasons.append("plan_indicates_production_mutation")
        if not plan.post_promotion_verification_plan:
            reasons.append("missing_post_promotion_verification_plan")
        if not plan.branch_allowed:
            reasons.append("target_branch_not_allowed")
        if not plan.ci_success:
            reasons.append("ci_not_successful")
        if not plan.rollback_verified:
            reasons.append("rollback_not_verified")

    if approval is None:
        pass
    elif plan is not None:
        if approval.release_id != release_id:
            reasons.append("approval_release_id_mismatch")
        if approval.run_id != plan.run_id:
            reasons.append("approval_run_id_mismatch")
        if approval.approved_action != "promote_release_candidate_to_production":
            reasons.append("approval_action_mismatch")
        if approval.release_plan_hash != plan_hash:
            reasons.append("approval_release_plan_hash_mismatch")
        if approval.target_branch != plan.target_branch:
            reasons.append("approval_target_branch_mismatch")

    status = ReleaseCandidateStatus.BLOCKED if reasons else ReleaseCandidateStatus.READY
    readiness = ProductionPromotionReadiness(
        release_id=release_id,
        run_id=plan.run_id if plan is not None else None,
        status=status,
        target_branch=plan.target_branch if plan is not None else None,
        release_plan_hash=plan_hash,
        approval_id=approval.approval_id if approval is not None else None,
        approval_applies=status == ReleaseCandidateStatus.READY,
        reason_codes=reasons if reasons else ["production_promotion_approval_applies", "dry_run_no_production_mutation"],
        post_promotion_verification_plan=plan.post_promotion_verification_plan if plan is not None else [],
        dry_run=True,
        production_mutated=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    _write_json(release_candidate_dir(root, release_id) / "readiness.json", readiness.model_dump(mode="json"))
    return readiness


def _ci_success(payload: dict[str, object]) -> bool:
    for key in ("status", "conclusion", "result"):
        value = payload.get(key)
        if isinstance(value, str) and value.lower() in {"success", "succeeded", "passed", "pass"}:
            return True
    return payload.get("success") is True or payload.get("passed") is True


def _check_passed(payload: dict[str, object]) -> bool:
    for key in ("bucket", "state", "conclusion", "status"):
        value = payload.get(key)
        if isinstance(value, str) and value.lower() in {"pass", "passed", "success", "succeeded"}:
            return True
    return payload.get("success") is True or payload.get("passed") is True


def _target_branch(evidence: dict[str, object]) -> str | None:
    value = evidence.get("target_branch")
    if isinstance(value, str) and value:
        return value
    promotion_result = evidence.get("promotion_result")
    if isinstance(promotion_result, dict):
        nested = promotion_result.get("target_branch")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
