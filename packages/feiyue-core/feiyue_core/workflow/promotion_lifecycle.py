from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel


class PromotionLifecycleStatus(StrEnum):
    PLANNED = "planned"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    FAILED = "failed"


class DraftPRStatus(StrEnum):
    CREATED = "created"
    BLOCKED = "blocked"


class PromotionPRPlan(FeiyueModel):
    """Provider-free local evidence for a PR that a human/tool may open later."""

    run_id: str
    task_id: str | None = None
    status: PromotionLifecycleStatus
    title: str
    body: str
    source_branch: str | None = None
    target_branch: str | None = None
    promoted_commit: str | None = None
    rollback_ref: str | None = None
    evidence_refs: dict[str, str] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    external_pr_created: bool = False
    draft: bool = True
    auto_merge: bool = False
    mutates_production: bool = False
    plan_hash: str | None = None
    written_at: str | None = None


class DraftPRApproval(FeiyueModel):
    """Exact human approval for creating a draft PR from a local PR plan."""

    approval_id: str
    approved_by: str
    run_id: str
    approved_action: str
    plan_hash: str
    source_branch: str
    target_branch: str
    rollback_ref: str
    approved_at: str
    reason: str

    @field_validator(
        "approval_id",
        "approved_by",
        "run_id",
        "approved_action",
        "plan_hash",
        "source_branch",
        "target_branch",
        "rollback_ref",
        "approved_at",
        "reason",
    )
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class DraftPREvidence(FeiyueModel):
    run_id: str
    status: DraftPRStatus
    adapter: str = "fake"
    source_branch: str | None = None
    target_branch: str | None = None
    rollback_ref: str | None = None
    plan_hash: str | None = None
    approval_applies: bool
    reason_codes: list[str] = Field(default_factory=list)
    external_pr_created: bool = False
    draft: bool = True
    auto_merge: bool = False
    mutates_production: bool = False
    pr_number: int | None = None
    pr_url: str | None = None
    approval_id: str | None = None
    written_at: str | None = None


class DraftPRAdapter:
    name = "fake"

    def create_draft_pr(self, *, plan: PromotionPRPlan) -> dict[str, object]:
        raise NotImplementedError


class FakeDraftPRAdapter(DraftPRAdapter):
    """Fake-first adapter: records intent but never opens an external PR."""

    name = "fake"

    def create_draft_pr(self, *, plan: PromotionPRPlan) -> dict[str, object]:
        return {
            "external_pr_created": False,
            "draft": True,
            "auto_merge": False,
            "mutates_production": False,
            "pr_number": None,
            "pr_url": f"fake://draft-pr/{plan.run_id}",
        }


class RollbackSandboxEvidence(FeiyueModel):
    """Local-only rollback simulation evidence for a promoted workflow run."""

    run_id: str
    task_id: str | None = None
    status: PromotionLifecycleStatus
    target_branch: str | None = None
    sandbox_branch: str
    rollback_ref: str | None = None
    verifier_command: str
    verifier_exit_code: int | None = None
    verifier_stdout: str = ""
    verifier_stderr: str = ""
    reason_codes: list[str] = Field(default_factory=list)
    repo_clean_before: bool
    repo_clean_after: bool | None = None
    sandbox_worktree_removed: bool = True
    external_side_effect_performed: bool = False
    written_at: str | None = None


class PromotionLifecycleError(RuntimeError):
    """Raised when the promotion lifecycle contract cannot be satisfied."""


def promotion_lifecycle_dir(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root) / ".hermes" / "promotion-lifecycle" / run_id


def create_multi_student_pr_plan(
    *,
    project_root: str | Path,
    run_id: str,
    source_branch: str,
    target_branch: str,
    title_prefix: str = "Create PR from verified true multi-student dry-run",
) -> PromotionPRPlan:
    """Create a local-only draft PR plan from verified true multi-student evidence.

    This is the 6A bridge after true multi-student dry-runs: it prepares a PR
    plan and exact-approval target without opening any external PR, merging, or
    mutating production. The existing approve/create draft PR gate then enforces
    the plan hash before fake-first PR evidence is emitted.
    """

    root = Path(project_root)
    evidence_path = root / ".hermes" / "multi-student-workflows" / run_id / "evidence.json"
    reason_codes: list[str] = []
    evidence: dict[str, object] = {}
    if not evidence_path.exists():
        reason_codes.append("missing_multi_student_evidence")
    else:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence.get("status") != "verified":
            reason_codes.append("multi_student_run_not_verified")
        if evidence.get("dry_run_only") is not True:
            reason_codes.append("multi_student_run_not_dry_run_only")
        if evidence.get("promotion_attempted") is not False:
            reason_codes.append("multi_student_run_attempted_promotion")
        if evidence.get("global_hermes_config_mutated") is not False:
            reason_codes.append("multi_student_run_mutated_global_config")

    rollback_ref = _safe_current_head(root)
    raw_task_id = evidence.get("task_id")
    task_id = raw_task_id if isinstance(raw_task_id, str) else None
    status = PromotionLifecycleStatus.BLOCKED if reason_codes else PromotionLifecycleStatus.PLANNED
    title = f"{title_prefix}: {run_id}"
    body_lines = [
        f"# True multi-student PR plan: {run_id}",
        "",
        "This is a local-only PR plan from verified true multi-student dry-run evidence.",
        "No GitHub API call, merge, deployment, or production mutation was performed.",
        "",
        f"task_id: {task_id or 'unknown'}",
        f"source_branch: {source_branch}",
        f"target_branch: {target_branch}",
        f"rollback_ref: {rollback_ref or 'unknown'}",
        f"evidence_path: {_rel(root, evidence_path) if evidence_path.exists() else 'missing'}",
        "",
        "## Reason codes",
        *[f"- {reason}" for reason in reason_codes],
        "",
    ]
    plan = PromotionPRPlan(
        run_id=run_id,
        task_id=task_id,
        status=status,
        title=title,
        body="\n".join(body_lines),
        source_branch=source_branch,
        target_branch=target_branch,
        promoted_commit=None,
        rollback_ref=rollback_ref,
        evidence_refs={"multi_student_evidence": _rel(root, evidence_path)} if evidence_path.exists() else {},
        reason_codes=reason_codes,
        external_pr_created=False,
        draft=True,
        auto_merge=False,
        mutates_production=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    plan.plan_hash = compute_pr_plan_hash(plan)
    _write_json(promotion_lifecycle_dir(root, run_id) / "pr-plan.json", plan.model_dump(mode="json"))
    return plan


def create_promotion_pr_plan(
    *,
    project_root: str | Path,
    run_id: str,
    allowed_target_branches: list[str],
    title_prefix: str = "Promote verified workflow run",
    source_branch: str | None = None,
) -> PromotionPRPlan:
    """Write a local PR plan from promotion evidence without opening a real PR.

    This function intentionally performs no network/API action. It fails closed by
    writing a blocked plan when required evidence is missing, the repo is dirty,
    the promotion was not successful, the promoted commit is missing, or the
    target branch is not allowlisted.
    """

    root = Path(project_root)
    evidence_path = _promotion_evidence_path(root, run_id)
    reason_codes: list[str] = []
    evidence: dict[str, object] = {}
    if not evidence_path.exists():
        reason_codes.append("missing_promotion_evidence")
    else:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    repo_clean = _repo_clean(root)
    if not repo_clean:
        reason_codes.append("source_repo_dirty_before")

    target_branch = _target_branch(evidence)
    promoted_commit = _promoted_commit(evidence)
    rollback_ref = _rollback_ref(evidence)
    resolved_source_branch = source_branch or _current_branch(root)
    raw_task_id = evidence.get("task_id")
    task_id = raw_task_id if isinstance(raw_task_id, str) else None

    if evidence and evidence.get("status") != "promoted":
        reason_codes.append("promotion_not_promoted")
    if evidence and not promoted_commit:
        reason_codes.append("missing_promoted_commit")
    if evidence and not target_branch:
        reason_codes.append("missing_target_branch")
    if target_branch and target_branch not in allowed_target_branches:
        reason_codes.append("target_branch_not_allowed")

    status = PromotionLifecycleStatus.BLOCKED if reason_codes else PromotionLifecycleStatus.PLANNED
    title = f"{title_prefix}: {run_id}"
    body = _render_pr_plan_body(
        run_id=run_id,
        task_id=task_id,
        source_branch=resolved_source_branch,
        target_branch=target_branch,
        promoted_commit=promoted_commit,
        rollback_ref=rollback_ref,
        evidence_path=evidence_path,
        status=status,
        reason_codes=reason_codes,
    )
    plan = PromotionPRPlan(
        run_id=run_id,
        task_id=task_id,
        status=status,
        title=title,
        body=body,
        source_branch=resolved_source_branch,
        target_branch=target_branch,
        promoted_commit=promoted_commit,
        rollback_ref=rollback_ref,
        evidence_refs={"promotion_evidence": _rel(root, evidence_path)} if evidence_path.exists() else {},
        reason_codes=reason_codes,
        external_pr_created=False,
        draft=True,
        auto_merge=False,
        mutates_production=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    plan.plan_hash = compute_pr_plan_hash(plan)
    _write_json(promotion_lifecycle_dir(root, run_id) / "pr-plan.json", plan.model_dump(mode="json"))
    return plan


def read_promotion_pr_plan(project_root: str | Path, run_id: str) -> PromotionPRPlan:
    path = promotion_lifecycle_dir(project_root, run_id) / "pr-plan.json"
    if not path.exists():
        raise FileNotFoundError(f"Promotion PR plan not found for run_id: {run_id}")
    return PromotionPRPlan.model_validate_json(path.read_text(encoding="utf-8"))


def compute_pr_plan_hash(plan: PromotionPRPlan) -> str:
    payload = plan.model_dump(mode="json")
    payload["written_at"] = None
    payload["plan_hash"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approve_draft_pr(
    *,
    project_root: str | Path,
    run_id: str,
    approved_by: str,
    approval_id: str,
    reason: str,
) -> DraftPRApproval:
    plan = read_promotion_pr_plan(project_root, run_id)
    plan_hash = plan.plan_hash or compute_pr_plan_hash(plan)
    approval = DraftPRApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        run_id=run_id,
        approved_action="create_draft_pr",
        plan_hash=plan_hash,
        source_branch=plan.source_branch or "",
        target_branch=plan.target_branch or "",
        rollback_ref=plan.rollback_ref or "",
        approved_at=datetime.now(UTC).isoformat(),
        reason=reason,
    )
    write_draft_pr_approval(project_root, approval)
    return approval


def write_draft_pr_approval(project_root: str | Path, approval: DraftPRApproval) -> Path:
    path = promotion_lifecycle_dir(project_root, approval.run_id) / "draft-pr-approval.json"
    _write_json(path, approval.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()})
    return path


def read_draft_pr_approval(project_root: str | Path, run_id: str) -> DraftPRApproval:
    path = promotion_lifecycle_dir(project_root, run_id) / "draft-pr-approval.json"
    if not path.exists():
        raise FileNotFoundError(f"Draft PR approval not found for run_id: {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("written_at", None)
    return DraftPRApproval.model_validate(payload)


def create_approved_draft_pr(
    *,
    project_root: str | Path,
    run_id: str,
    approval: DraftPRApproval | None,
    adapter: DraftPRAdapter | None = None,
) -> DraftPREvidence:
    plan: PromotionPRPlan | None = None
    reasons: list[str] = []
    try:
        plan = read_promotion_pr_plan(project_root, run_id)
    except FileNotFoundError:
        reasons.append("missing_pr_plan")

    plan_hash = plan.plan_hash or compute_pr_plan_hash(plan) if plan is not None else None
    if plan is not None:
        if plan.status != PromotionLifecycleStatus.PLANNED:
            reasons.append("pr_plan_not_planned")
        if not plan.source_branch:
            reasons.append("missing_source_branch")
        if not plan.target_branch:
            reasons.append("missing_target_branch")
        if not plan.rollback_ref:
            reasons.append("missing_rollback_ref")

    if approval is None:
        reasons.append("missing_draft_pr_approval")
    elif plan is not None:
        if approval.run_id != run_id:
            reasons.append("approval_run_id_mismatch")
        if approval.approved_action != "create_draft_pr":
            reasons.append("approval_action_mismatch")
        if approval.plan_hash != plan_hash:
            reasons.append("approval_plan_hash_mismatch")
        if approval.source_branch != plan.source_branch:
            reasons.append("approval_source_branch_mismatch")
        if approval.target_branch != plan.target_branch:
            reasons.append("approval_target_branch_mismatch")
        if approval.rollback_ref != plan.rollback_ref:
            reasons.append("approval_rollback_ref_mismatch")

    if reasons:
        evidence = DraftPREvidence(
            run_id=run_id,
            status=DraftPRStatus.BLOCKED,
            adapter=(adapter or FakeDraftPRAdapter()).name,
            source_branch=plan.source_branch if plan is not None else None,
            target_branch=plan.target_branch if plan is not None else None,
            rollback_ref=plan.rollback_ref if plan is not None else None,
            plan_hash=plan_hash,
            approval_applies=False,
            reason_codes=reasons,
            approval_id=approval.approval_id if approval is not None else None,
            written_at=datetime.now(UTC).isoformat(),
        )
        _write_json(promotion_lifecycle_dir(project_root, run_id) / "draft-pr-evidence.json", evidence.model_dump(mode="json"))
        return evidence

    assert plan is not None
    adapter = adapter or FakeDraftPRAdapter()
    created = adapter.create_draft_pr(plan=plan)
    evidence = DraftPREvidence(
        run_id=run_id,
        status=DraftPRStatus.CREATED,
        adapter=adapter.name,
        source_branch=plan.source_branch,
        target_branch=plan.target_branch,
        rollback_ref=plan.rollback_ref,
        plan_hash=plan_hash,
        approval_applies=True,
        reason_codes=["draft_pr_approval_applies", "fake_adapter_no_external_pr_created"] if adapter.name == "fake" else ["draft_pr_approval_applies"],
        external_pr_created=bool(created.get("external_pr_created", False)),
        draft=bool(created.get("draft", True)),
        auto_merge=bool(created.get("auto_merge", False)),
        mutates_production=bool(created.get("mutates_production", False)),
        pr_number=created.get("pr_number") if isinstance(created.get("pr_number"), int) else None,
        pr_url=created.get("pr_url") if isinstance(created.get("pr_url"), str) else None,
        approval_id=approval.approval_id if approval is not None else None,
        written_at=datetime.now(UTC).isoformat(),
    )
    _write_json(promotion_lifecycle_dir(project_root, run_id) / "draft-pr-evidence.json", evidence.model_dump(mode="json"))
    return evidence


def simulate_rollback_sandbox(
    *,
    project_root: str | Path,
    run_id: str,
    allowed_target_branches: list[str],
    verifier_command: str,
    sandbox_branch: str | None = None,
) -> RollbackSandboxEvidence:
    """Checkout/reset a local sandbox branch to rollback_ref and run verifier.

    No remotes, GitHub APIs, pushes, or PR creation are used. The caller receives
    persisted evidence under .hermes/promotion-lifecycle/<run_id>/rollback-evidence.json.
    """

    root = Path(project_root)
    evidence_path = _promotion_evidence_path(root, run_id)
    reason_codes: list[str] = []
    evidence: dict[str, object] = {}
    if not evidence_path.exists():
        reason_codes.append("missing_promotion_evidence")
    else:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    repo_clean_before = _repo_clean(root)
    if not repo_clean_before:
        reason_codes.append("source_repo_dirty_before")

    target_branch = _target_branch(evidence)
    rollback_ref = _rollback_ref(evidence)
    raw_task_id = evidence.get("task_id")
    task_id = raw_task_id if isinstance(raw_task_id, str) else None
    branch = sandbox_branch or f"hermes/rollback-sandbox/{run_id}"

    if evidence and evidence.get("status") != "promoted":
        reason_codes.append("promotion_not_promoted")
    if target_branch and target_branch not in allowed_target_branches:
        reason_codes.append("target_branch_not_allowed")
    if evidence and not target_branch:
        reason_codes.append("missing_target_branch")
    if evidence and not rollback_ref:
        reason_codes.append("missing_rollback_ref")
    if rollback_ref and not _git_ref_exists(root, rollback_ref):
        reason_codes.append("rollback_ref_not_found")

    if reason_codes:
        result = RollbackSandboxEvidence(
            run_id=run_id,
            task_id=task_id,
            status=PromotionLifecycleStatus.BLOCKED,
            target_branch=target_branch,
            sandbox_branch=branch,
            rollback_ref=rollback_ref,
            verifier_command=verifier_command,
            reason_codes=reason_codes,
            repo_clean_before=repo_clean_before,
            repo_clean_after=_repo_clean(root),
            sandbox_worktree_removed=True,
            written_at=datetime.now(UTC).isoformat(),
        )
        _write_json(promotion_lifecycle_dir(root, run_id) / "rollback-evidence.json", result.model_dump(mode="json"))
        return result

    worktree_path = Path(tempfile.mkdtemp(prefix="feiyue-rollback-sandbox-"))
    removed = False
    verifier_exit_code: int | None = None
    stdout = ""
    stderr = ""
    status = PromotionLifecycleStatus.FAILED
    try:
        assert rollback_ref is not None
        _git(root, "worktree", "add", "-B", branch, str(worktree_path), rollback_ref)
        completed = subprocess.run(
            shlex.split(verifier_command),
            cwd=worktree_path,
            text=True,
            capture_output=True,
            check=False,
        )
        verifier_exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        status = PromotionLifecycleStatus.VERIFIED if completed.returncode == 0 else PromotionLifecycleStatus.FAILED
        if completed.returncode != 0:
            reason_codes.append("verifier_failed")
    except Exception as exc:
        reason_codes.append("rollback_sandbox_failed")
        stderr = str(exc)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree_path)], cwd=root, text=True, capture_output=True, check=False)
        removed = not worktree_path.exists()

    result = RollbackSandboxEvidence(
        run_id=run_id,
        task_id=task_id,
        status=status,
        target_branch=target_branch,
        sandbox_branch=branch,
        rollback_ref=rollback_ref,
        verifier_command=verifier_command,
        verifier_exit_code=verifier_exit_code,
        verifier_stdout=stdout,
        verifier_stderr=stderr,
        reason_codes=reason_codes,
        repo_clean_before=repo_clean_before,
        repo_clean_after=_repo_clean(root),
        sandbox_worktree_removed=removed,
        written_at=datetime.now(UTC).isoformat(),
    )
    _write_json(promotion_lifecycle_dir(root, run_id) / "rollback-evidence.json", result.model_dump(mode="json"))
    return result


def _promotion_evidence_path(root: Path, run_id: str) -> Path:
    return root / ".hermes" / "workflow-promotions" / run_id / "promotion-evidence.json"


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


def _promoted_commit(evidence: dict[str, object]) -> str | None:
    promotion_result = evidence.get("promotion_result")
    if isinstance(promotion_result, dict):
        value = promotion_result.get("commit_sha")
        if isinstance(value, str) and value:
            return value
    value = evidence.get("promoted_commit")
    return value if isinstance(value, str) and value else None


def _rollback_ref(evidence: dict[str, object]) -> str | None:
    promotion_result = evidence.get("promotion_result")
    if isinstance(promotion_result, dict):
        value = promotion_result.get("rollback_ref")
        if isinstance(value, str) and value:
            return value
    value = evidence.get("rollback_ref")
    return value if isinstance(value, str) and value else None


def _render_pr_plan_body(
    *,
    run_id: str,
    task_id: str | None,
    source_branch: str | None,
    target_branch: str | None,
    promoted_commit: str | None,
    rollback_ref: str | None,
    evidence_path: Path,
    status: PromotionLifecycleStatus,
    reason_codes: list[str],
) -> str:
    lines = [
        "# Promotion PR Plan",
        "",
        f"- run_id: {run_id}",
        f"- task_id: {task_id or 'None'}",
        f"- status: {status.value}",
        f"- source_branch: {source_branch or 'None'}",
        f"- target_branch: {target_branch or 'None'}",
        f"- promoted_commit: {promoted_commit or 'None'}",
        f"- rollback_ref: {rollback_ref or 'None'}",
        f"- promotion_evidence: {evidence_path}",
        "- external_pr_created: false",
    ]
    if reason_codes:
        lines.extend(["", "## Blockers", *[f"- {reason}" for reason in reason_codes]])
    else:
        lines.extend(
            [
                "",
                "## Contract",
                "- This is a local PR plan only; no GitHub API call, remote push, or real PR was created.",
                "- Use the evidence refs to review the promoted commit and rollback ref before any external action.",
            ]
        )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _current_branch(root: Path) -> str | None:
    completed = subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=False)
    branch = completed.stdout.strip()
    return branch or None


def _safe_current_head(root: Path) -> str | None:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _repo_clean(root: Path) -> bool:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=False)
    return completed.returncode == 0 and completed.stdout == ""


def _git_ref_exists(root: Path, ref: str) -> bool:
    completed = subprocess.run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=root, text=True, capture_output=True, check=False)
    return completed.returncode == 0


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise PromotionLifecycleError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
