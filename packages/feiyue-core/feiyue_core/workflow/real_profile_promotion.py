from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.execution import CandidateFileWrite, PromotionResult, PromotionStatus, ToyWorkflowExecutor, WorkflowExecutionReport
from feiyue_core.workflow.real_profile_workflow_runner import RealProfileWorkflowRunReport, RealProfileWorkflowStatus


class RealProfilePromotionStatus(StrEnum):
    PROMOTED = "promoted"
    BLOCKED = "blocked"
    FAILED = "failed"


class RealProfilePromotionApproval(FeiyueModel):
    """Exact human approval record for promoting a verified real-profile dry run."""

    approval_id: str
    approved_by: str
    run_id: str
    task_id: str
    approved_action: str
    changed_files: list[str]
    target_branch: str
    source_commit_sha: str
    workflow_report_hash: str
    approved_at: str
    reason: str

    @field_validator(
        "approval_id",
        "approved_by",
        "run_id",
        "task_id",
        "approved_action",
        "target_branch",
        "source_commit_sha",
        "workflow_report_hash",
        "approved_at",
        "reason",
    )
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("changed_files")
    @classmethod
    def _non_empty_changed_files(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("changed_files must contain non-empty paths")
        return normalized


class RealProfilePromotionGateResult(FeiyueModel):
    run_id: str
    task_id: str
    status: RealProfilePromotionStatus
    target_branch: str
    approval_applies: bool
    promotion_attempted: bool
    reason_codes: list[str]
    source_repo_clean: bool
    promotion_result: PromotionResult | None = None
    approval_id: str | None = None
    written_at: str | None = None


def approval_evidence_path(evidence_root: str | Path, run_id: str) -> Path:
    return Path(evidence_root) / ".hermes" / "workflow-promotions" / run_id / "approval.json"


def write_promotion_approval(approval: RealProfilePromotionApproval, evidence_root: str | Path) -> Path:
    path = approval_evidence_path(evidence_root, approval.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = approval.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_promotion_approval(evidence_root: str | Path, run_id: str) -> RealProfilePromotionApproval:
    path = approval_evidence_path(evidence_root, run_id)
    if not path.exists():
        raise FileNotFoundError(f"Promotion approval evidence not found for run_id: {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("written_at", None)
    return RealProfilePromotionApproval.model_validate(payload)


class RealProfilePromotionGate:
    """Fail-closed promotion boundary for Wave4-3B real-profile dry runs."""

    def __init__(self, *, workflow_executor: ToyWorkflowExecutor | None = None) -> None:
        self._workflow_executor = workflow_executor or ToyWorkflowExecutor()

    def promote_verified_dry_run(
        self,
        *,
        source_repo: str | Path,
        dry_run_report: RealProfileWorkflowRunReport,
        candidate_writes: list[CandidateFileWrite],
        target_branch: str,
        commit_message: str,
        approval: RealProfilePromotionApproval | None,
        evidence_root: str | Path,
    ) -> RealProfilePromotionGateResult:
        source_path = Path(source_repo)
        reason_codes = self._approval_failures(
            source_path=source_path,
            dry_run_report=dry_run_report,
            candidate_writes=candidate_writes,
            target_branch=target_branch,
            approval=approval,
        )
        approval_applies = not reason_codes
        if not approval_applies:
            result = RealProfilePromotionGateResult(
                run_id=dry_run_report.run_id,
                task_id=dry_run_report.task_id,
                status=RealProfilePromotionStatus.BLOCKED,
                target_branch=target_branch,
                approval_applies=False,
                promotion_attempted=False,
                reason_codes=reason_codes,
                source_repo_clean=_source_repo_clean(source_path),
                approval_id=approval.approval_id if approval is not None else None,
            )
            self._write_evidence(result, evidence_root)
            return result

        assert dry_run_report.workflow_report is not None
        promotion = self._workflow_executor.promote_verified_writes(
            source_repo=source_path,
            report=dry_run_report.workflow_report,
            candidate_writes=candidate_writes,
            target_branch=target_branch,
            commit_message=commit_message,
        )
        status = (
            RealProfilePromotionStatus.PROMOTED
            if promotion.status == PromotionStatus.PROMOTED
            else RealProfilePromotionStatus.BLOCKED
            if promotion.status == PromotionStatus.BLOCKED
            else RealProfilePromotionStatus.FAILED
        )
        result = RealProfilePromotionGateResult(
            run_id=dry_run_report.run_id,
            task_id=dry_run_report.task_id,
            status=status,
            target_branch=target_branch,
            approval_applies=True,
            promotion_attempted=True,
            reason_codes=["promotion_approval_applies"],
            source_repo_clean=_source_repo_clean(source_path),
            promotion_result=promotion,
            approval_id=approval.approval_id if approval is not None else None,
        )
        self._write_evidence(result, evidence_root)
        return result

    def _approval_failures(
        self,
        *,
        source_path: Path,
        dry_run_report: RealProfileWorkflowRunReport,
        candidate_writes: list[CandidateFileWrite],
        target_branch: str,
        approval: RealProfilePromotionApproval | None,
    ) -> list[str]:
        if approval is None:
            return ["missing_promotion_approval"]
        reasons: list[str] = []
        workflow_report = dry_run_report.workflow_report
        if dry_run_report.status != RealProfileWorkflowStatus.VERIFIED or workflow_report is None:
            reasons.append("dry_run_not_verified")
        elif not workflow_report.promotion_ready or not workflow_report.verification_passed:
            reasons.append("workflow_report_not_promotion_ready")
        if not dry_run_report.dry_run_only:
            reasons.append("source_run_not_dry_run")
        if dry_run_report.promotion_attempted:
            reasons.append("source_run_already_attempted_promotion")
        if approval.run_id != dry_run_report.run_id:
            reasons.append("run_id_mismatch")
        if approval.task_id != dry_run_report.task_id:
            reasons.append("task_id_mismatch")
        if approval.approved_action != "promote_verified_dry_run":
            reasons.append("approved_action_mismatch")
        changed_files = [write.path for write in candidate_writes]
        if approval.changed_files != changed_files:
            reasons.append("changed_files_mismatch")
        if workflow_report is not None and workflow_report.changed_files != changed_files:
            reasons.append("workflow_changed_files_mismatch")
        if approval.target_branch != target_branch:
            reasons.append("target_branch_mismatch")
        source_sha = _git("rev-parse", "HEAD", cwd=source_path).strip() if _source_repo_clean(source_path) else None
        if source_sha is None:
            reasons.append("source_repo_dirty_before")
        elif approval.source_commit_sha != source_sha:
            reasons.append("source_commit_sha_mismatch")
        if workflow_report is not None and approval.workflow_report_hash != compute_workflow_report_hash(workflow_report):
            reasons.append("workflow_report_hash_mismatch")
        return reasons

    @staticmethod
    def _write_evidence(result: RealProfilePromotionGateResult, evidence_root: str | Path) -> Path:
        evidence_dir = Path(evidence_root) / ".hermes" / "workflow-promotions" / result.run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        payload = result.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()}
        evidence_path = evidence_dir / "promotion-evidence.json"
        evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return evidence_path


def compute_workflow_report_hash(report: WorkflowExecutionReport) -> str:
    payload = json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_repo_clean(source_path: Path) -> bool:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=source_path, text=True, capture_output=True, check=False)
    return completed.returncode == 0 and completed.stdout == ""


def _git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout
