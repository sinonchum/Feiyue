from __future__ import annotations

import hashlib
import json
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
