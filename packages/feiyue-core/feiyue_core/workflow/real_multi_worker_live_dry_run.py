"""Authorized real multi-worker live dry-run evidence seam.

Wave5-3 productizes the *evidence path* for an explicitly authorized Hermes
multi-worker dry-run without requiring tests to make live Hermes/provider calls.
The executor is fake-first, fail-closed, dry-run-only, and writes history-compatible
evidence under `.hermes/real-multi-worker-runs/<run_id>/evidence.json`.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlan
from feiyue_core.workflow.multi_worker_workflow_dry_run import (
    MultiWorkerTeacherEscalationAuthorization,
    MultiWorkerWorkflowDryRunAuthorization,
    MultiWorkerWorkflowDryRunOrchestrator,
    MultiWorkerWorkflowDryRunReport,
    MultiWorkerWorkflowDryRunStatus,
)
from feiyue_core.workflow.profile_worker_bridge import ProfileRunnerLike
from feiyue_core.workflow.task_contract import TaskContract


class RealMultiWorkerLiveDryRunStatus(StrEnum):
    VERIFIED = "verified"
    NEEDS_TEACHER = "needs_teacher"
    BLOCKED = "blocked"


class RealMultiWorkerLiveDryRunAuthorization(FeiyueModel):
    """Exact local approval for one real Hermes multi-worker live dry-run."""

    authorization_id: str
    authorized_by: str
    plan_id: str
    run_id: str
    task_id: str
    approved_action: str = "execute_real_multi_worker_live_dry_run"
    worker_profile_id: str
    scopes: list[str]
    max_profile_calls: int = Field(default=1, ge=0)
    budget_ceiling: str
    dry_run_only: bool = True
    promotion_disabled: bool = True
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator(
        "authorization_id",
        "authorized_by",
        "plan_id",
        "run_id",
        "task_id",
        "approved_action",
        "worker_profile_id",
        "budget_ceiling",
        "reason",
    )
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("real multi-worker authorization text fields must be non-empty")
        return normalized

    @field_validator("scopes")
    @classmethod
    def _required_scopes(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("real multi-worker authorization scopes must contain non-empty strings")
        return normalized

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


class RealMultiWorkerTeacherEscalationAuthorization(FeiyueModel):
    """Separate exact approval for optional teacher escalation in the live dry-run."""

    authorization_id: str
    authorized_by: str
    plan_id: str
    run_id: str
    task_id: str
    approved_action: str = "execute_real_multi_worker_teacher_escalation_dry_run"
    worker_profile_id: str
    teacher_profile_id: str
    scopes: list[str]
    max_profile_calls: int = Field(default=3, ge=0)
    budget_ceiling: str
    dry_run_only: bool = True
    promotion_disabled: bool = True
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator(
        "authorization_id",
        "authorized_by",
        "plan_id",
        "run_id",
        "task_id",
        "approved_action",
        "worker_profile_id",
        "teacher_profile_id",
        "budget_ceiling",
        "reason",
    )
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("real multi-worker teacher authorization text fields must be non-empty")
        return normalized

    @field_validator("scopes")
    @classmethod
    def _required_scopes(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("real multi-worker teacher authorization scopes must contain non-empty strings")
        return normalized

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


class RealMultiWorkerLiveDryRunEvidence(FeiyueModel):
    run_id: str
    task_id: str
    plan_id: str
    source_kind: str = "real_multi_worker_live_dry_run"
    status: RealMultiWorkerLiveDryRunStatus
    verified: bool = False
    worker_profile: str | None = None
    teacher_profile: str | None = None
    provider_call_count: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    source_clean: bool = False
    source_repo_clean: bool = False
    dry_run_only: bool = True
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    route_plan_status: str
    routing_apply_evidence_id: str | None = None
    authorization_id: str | None = None
    teacher_authorization_id: str | None = None
    reason_codes: list[str]
    dry_run_report: MultiWorkerWorkflowDryRunReport | None = None
    started_at: str
    completed_at: str

    @field_validator("run_id", "task_id", "plan_id", "route_plan_status", "started_at", "completed_at")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("real multi-worker evidence strings must be non-empty")
        return normalized

    @field_validator("reason_codes")
    @classmethod
    def _required_reasons(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("real multi-worker evidence reason_codes must contain non-empty strings")
        return normalized


class RealMultiWorkerLiveDryRunExecutor:
    """Run the authorized seam with an injected runner and fail closed before calls."""

    def __init__(self, *, profile_runner: ProfileRunnerLike) -> None:
        self._profile_runner = profile_runner

    def run(
        self,
        *,
        project_root: str | Path,
        source_repo: str | Path,
        contract: TaskContract,
        project_name: str,
        plan: MultiWorkerOrchestrationPlan,
        authorization: RealMultiWorkerLiveDryRunAuthorization | None,
        run_id: str,
        teacher_escalation_authorization: RealMultiWorkerTeacherEscalationAuthorization | None = None,
        cost_usd: float = 0,
        latency_ms: float = 0,
    ) -> RealMultiWorkerLiveDryRunEvidence:
        started_at = datetime.now(UTC).isoformat()
        root = Path(project_root)
        source_path = Path(source_repo)
        source_clean = _source_repo_clean(source_path)
        block_reasons = _authorization_block_reasons(
            plan=plan,
            contract=contract,
            authorization=authorization,
            run_id=run_id,
        )
        if block_reasons:
            evidence = RealMultiWorkerLiveDryRunEvidence(
                run_id=run_id,
                task_id=contract.task_id,
                plan_id=plan.plan_id,
                status=RealMultiWorkerLiveDryRunStatus.BLOCKED,
                verified=False,
                worker_profile=plan.route.worker_profile_ids[0] if plan.route.worker_profile_ids else None,
                teacher_profile=plan.route.teacher_profile_id,
                provider_call_count=0,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                source_clean=source_clean,
                source_repo_clean=source_clean,
                dry_run_only=True,
                promotion_attempted=False,
                global_hermes_config_mutated=False,
                route_plan_status=str(plan.route.status),
                routing_apply_evidence_id=plan.routing_apply_evidence_id,
                authorization_id=authorization.authorization_id if authorization is not None else None,
                reason_codes=_dedupe(block_reasons),
                started_at=started_at,
                completed_at=datetime.now(UTC).isoformat(),
            )
            self._write_evidence(evidence, root)
            return evidence

        assert authorization is not None
        worker_authorization = MultiWorkerWorkflowDryRunAuthorization(
            authorization_id=authorization.authorization_id,
            authorized_by=authorization.authorized_by,
            plan_id=authorization.plan_id,
            task_id=authorization.task_id,
            approved_action="execute_multi_worker_workflow_dry_run",
            worker_profile_ids=[authorization.worker_profile_id],
            scopes=["multi_worker_workflow_execute"],
            max_profile_calls=authorization.max_profile_calls,
            dry_run_only=True,
            approved_at=authorization.approved_at,
            reason=authorization.reason,
        )
        teacher_authorization = _to_multi_worker_teacher_authorization(
            authorization=teacher_escalation_authorization,
            expected_run_id=run_id,
            plan=plan,
            contract=contract,
        )
        dry_run_report = MultiWorkerWorkflowDryRunOrchestrator(profile_runner=self._profile_runner).run(
            project_root=root,
            source_repo=source_path,
            contract=contract,
            project_name=project_name,
            plan=plan,
            authorization=worker_authorization,
            run_id=run_id,
            teacher_escalation_authorization=teacher_authorization,
        )
        status = _map_status(dry_run_report.status)
        evidence = RealMultiWorkerLiveDryRunEvidence(
            run_id=run_id,
            task_id=contract.task_id,
            plan_id=plan.plan_id,
            status=status,
            verified=status == RealMultiWorkerLiveDryRunStatus.VERIFIED,
            worker_profile=dry_run_report.worker_profile,
            teacher_profile=dry_run_report.teacher_profile,
            provider_call_count=dry_run_report.provider_call_count,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            source_clean=source_clean,
            source_repo_clean=source_clean,
            dry_run_only=True,
            promotion_attempted=False,
            global_hermes_config_mutated=False,
            route_plan_status=dry_run_report.route_plan_status,
            routing_apply_evidence_id=dry_run_report.routing_apply_evidence_id,
            authorization_id=authorization.authorization_id,
            teacher_authorization_id=(
                teacher_escalation_authorization.authorization_id
                if teacher_authorization is not None and teacher_escalation_authorization is not None
                else None
            ),
            reason_codes=_dedupe(
                [
                    "real_multi_worker_live_dry_run_authorization_applies",
                    "real_multi_worker_live_dry_run_dry_run_only",
                    "real_multi_worker_live_dry_run_no_promotion",
                    *dry_run_report.reason_codes,
                ]
            ),
            dry_run_report=dry_run_report,
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
        )
        self._write_evidence(evidence, root)
        return evidence

    @staticmethod
    def _write_evidence(evidence: RealMultiWorkerLiveDryRunEvidence, project_root: Path) -> Path:
        evidence_dir = project_root / ".hermes" / "real-multi-worker-runs" / evidence.run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        payload = evidence.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()}
        evidence_path = evidence_dir / "evidence.json"
        evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (evidence_dir / "report.md").write_text(_render_markdown_report(evidence), encoding="utf-8")
        return evidence_path


def real_multi_worker_live_dry_run_evidence_path(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root) / ".hermes" / "real-multi-worker-runs" / run_id / "evidence.json"


def read_real_multi_worker_live_dry_run_evidence(project_root: str | Path, run_id: str) -> RealMultiWorkerLiveDryRunEvidence:
    path = real_multi_worker_live_dry_run_evidence_path(project_root, run_id)
    if not path.exists():
        raise FileNotFoundError(f"Real multi-worker live dry-run evidence not found for run_id: {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload.pop("written_at", None)
    return RealMultiWorkerLiveDryRunEvidence.model_validate(payload)


def _authorization_block_reasons(
    *,
    plan: MultiWorkerOrchestrationPlan,
    contract: TaskContract,
    authorization: RealMultiWorkerLiveDryRunAuthorization | None,
    run_id: str,
) -> list[str]:
    if authorization is None:
        return ["missing_real_multi_worker_live_dry_run_authorization"]
    reasons: list[str] = []
    if authorization.plan_id != plan.plan_id:
        reasons.append("authorization_plan_id_mismatch")
    if authorization.run_id != run_id:
        reasons.append("authorization_run_id_mismatch")
    if authorization.task_id != contract.task_id or authorization.task_id != plan.task_id:
        reasons.append("authorization_task_id_mismatch")
    if authorization.approved_action != "execute_real_multi_worker_live_dry_run":
        reasons.append("authorization_action_mismatch")
    worker_profile_ids = plan.route.worker_profile_ids
    if worker_profile_ids != [authorization.worker_profile_id]:
        reasons.append("authorization_worker_profile_id_mismatch")
    if not authorization.allows("real_multi_worker_live_dry_run_execute"):
        reasons.append("authorization_scope_real_multi_worker_live_dry_run_execute_missing")
    if not authorization.dry_run_only:
        reasons.append("authorization_must_be_dry_run_only")
    if not authorization.promotion_disabled:
        reasons.append("authorization_must_disable_promotion")
    if authorization.max_profile_calls < 1:
        reasons.append("max_profile_calls_would_be_exceeded")
    return reasons


def _to_multi_worker_teacher_authorization(
    *,
    authorization: RealMultiWorkerTeacherEscalationAuthorization | None,
    expected_run_id: str,
    plan: MultiWorkerOrchestrationPlan,
    contract: TaskContract,
) -> MultiWorkerTeacherEscalationAuthorization | None:
    if authorization is None:
        return None
    teacher_profile = plan.route.teacher_profile_id or plan.audit_metadata.get("available_teacher_profile_id")
    if not isinstance(teacher_profile, str) or not teacher_profile.strip():
        return None
    if authorization.plan_id != plan.plan_id or authorization.run_id != expected_run_id:
        return None
    if authorization.task_id != contract.task_id or authorization.task_id != plan.task_id:
        return None
    if authorization.approved_action != "execute_real_multi_worker_teacher_escalation_dry_run":
        return None
    if authorization.worker_profile_id != (plan.route.worker_profile_ids[0] if plan.route.worker_profile_ids else None):
        return None
    if authorization.teacher_profile_id != teacher_profile:
        return None
    if not authorization.dry_run_only or not authorization.promotion_disabled:
        return None
    if authorization.max_profile_calls < 3 or not authorization.allows("real_multi_worker_teacher_escalation"):
        return None
    return MultiWorkerTeacherEscalationAuthorization(
        authorization_id=authorization.authorization_id,
        authorized_by=authorization.authorized_by,
        plan_id=authorization.plan_id,
        task_id=authorization.task_id,
        approved_action="execute_multi_worker_teacher_escalation_retry",
        worker_profile_id=authorization.worker_profile_id,
        teacher_profile_id=authorization.teacher_profile_id,
        scopes=["teacher_escalation"],
        max_profile_calls=authorization.max_profile_calls,
        dry_run_only=True,
        approved_at=authorization.approved_at,
        reason=authorization.reason,
    )


def _source_repo_clean(source_path: Path) -> bool:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=source_path, text=True, capture_output=True, check=False)
    return completed.returncode == 0 and completed.stdout == ""


def _map_status(status: MultiWorkerWorkflowDryRunStatus) -> RealMultiWorkerLiveDryRunStatus:
    if status == MultiWorkerWorkflowDryRunStatus.VERIFIED:
        return RealMultiWorkerLiveDryRunStatus.VERIFIED
    if status == MultiWorkerWorkflowDryRunStatus.NEEDS_TEACHER:
        return RealMultiWorkerLiveDryRunStatus.NEEDS_TEACHER
    return RealMultiWorkerLiveDryRunStatus.BLOCKED


def _render_markdown_report(evidence: RealMultiWorkerLiveDryRunEvidence) -> str:
    return "\n".join(
        [
            f"# Real multi-worker live dry-run: {evidence.run_id}",
            "",
            f"task_id: {evidence.task_id}",
            f"plan_id: {evidence.plan_id}",
            f"status: {evidence.status}",
            f"worker_profile: {evidence.worker_profile or 'none'}",
            f"teacher_profile: {evidence.teacher_profile or 'none'}",
            f"provider_call_count: {evidence.provider_call_count}",
            f"cost_usd: {evidence.cost_usd}",
            f"latency_ms: {evidence.latency_ms}",
            f"source_clean: {str(evidence.source_clean).lower()}",
            f"dry_run_only: {str(evidence.dry_run_only).lower()}",
            f"promotion_attempted: {str(evidence.promotion_attempted).lower()}",
            f"global_hermes_config_mutated: {str(evidence.global_hermes_config_mutated).lower()}",
            "",
            "## Reason codes",
            *[f"- {reason}" for reason in evidence.reason_codes],
            "",
        ]
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
