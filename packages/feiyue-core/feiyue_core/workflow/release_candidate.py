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
