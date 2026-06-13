from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class PromotionLifecycleStatus(StrEnum):
    PLANNED = "planned"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    FAILED = "failed"


class PromotionPRPlan(FeiyueModel):
    """Provider-free local evidence for a PR that a human/tool may open later."""

    run_id: str
    task_id: str | None = None
    status: PromotionLifecycleStatus
    title: str
    body: str
    target_branch: str | None = None
    promoted_commit: str | None = None
    rollback_ref: str | None = None
    evidence_refs: dict[str, str] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    external_pr_created: bool = False
    written_at: str | None = None


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


def create_promotion_pr_plan(
    *,
    project_root: str | Path,
    run_id: str,
    allowed_target_branches: list[str],
    title_prefix: str = "Promote verified workflow run",
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
        target_branch=target_branch,
        promoted_commit=promoted_commit,
        rollback_ref=rollback_ref,
        evidence_refs={"promotion_evidence": _rel(root, evidence_path)} if evidence_path.exists() else {},
        reason_codes=reason_codes,
        external_pr_created=False,
        written_at=datetime.now(UTC).isoformat(),
    )
    _write_json(promotion_lifecycle_dir(root, run_id) / "pr-plan.json", plan.model_dump(mode="json"))
    return plan


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
