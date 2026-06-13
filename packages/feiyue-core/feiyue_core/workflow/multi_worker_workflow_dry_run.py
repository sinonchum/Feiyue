"""Approval-gated multi-worker workflow dry-run orchestration.

Wave4-5B connects an approved multi-worker route plan to the existing real/fake
profile workflow dry-run runner.  It remains deliberately dry-run only: provider
execution requires an exact local authorization, promotion is never attempted,
and global Hermes configuration is never mutated.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from feiyue_core.providers.authorization import AuthorizedProviderRunRecord
from feiyue_core.providers.profile_runner import FakeProfileRunner, HermesProfileSubprocessRunner
from feiyue_core.routing.multi_worker_gate import RouteStatus
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.execution import WorkflowExecutionReport
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlan
from feiyue_core.workflow.profile_worker_bridge import ProfileRunnerLike
from feiyue_core.workflow.real_profile_workflow_runner import (
    RealProfileWorkflowAuthorization,
    RealProfileWorkflowRunReport,
    RealProfileWorkflowRunner,
    RealProfileWorkflowStatus,
)
from feiyue_core.workflow.task_contract import TaskContract


class MultiWorkerWorkflowDryRunStatus(StrEnum):
    VERIFIED = "verified"
    NEEDS_TEACHER = "needs_teacher"
    BLOCKED = "blocked"


class MultiWorkerProfileRunnerMode(StrEnum):
    FAKE = "fake"
    HERMES = "hermes"


class MultiWorkerProfileRunnerSelectionError(ValueError):
    """Raised before any profile call when the requested runner is not authorized."""


class MultiWorkerWorkflowDryRunAuthorization(FeiyueModel):
    authorization_id: str
    authorized_by: str
    plan_id: str
    task_id: str
    approved_action: str
    worker_profile_ids: list[str]
    scopes: list[str]
    max_profile_calls: int = Field(default=1, ge=0)
    dry_run_only: bool = True
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator("authorization_id", "authorized_by", "plan_id", "task_id", "approved_action", "reason")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("authorization text fields must be non-empty")
        return normalized

    @field_validator("worker_profile_ids", "scopes")
    @classmethod
    def _required_string_list(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("authorization lists must contain non-empty strings")
        return normalized

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


class MultiWorkerTeacherEscalationAuthorization(FeiyueModel):
    """Separate exact approval for fake teacher guidance plus worker retry."""

    authorization_id: str
    authorized_by: str
    plan_id: str
    task_id: str
    approved_action: str = "execute_multi_worker_teacher_escalation_retry"
    worker_profile_id: str
    teacher_profile_id: str
    scopes: list[str]
    max_profile_calls: int = Field(default=3, ge=0)
    dry_run_only: bool = True
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator(
        "authorization_id",
        "authorized_by",
        "plan_id",
        "task_id",
        "approved_action",
        "worker_profile_id",
        "teacher_profile_id",
        "reason",
    )
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("teacher escalation authorization text fields must be non-empty")
        return normalized

    @field_validator("scopes")
    @classmethod
    def _required_scopes(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("teacher escalation authorization scopes must contain non-empty strings")
        return normalized

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


def multi_worker_dry_run_approval_path(project_root: str | Path, plan_id: str) -> Path:
    return Path(project_root) / ".hermes" / "multi-worker-plans" / plan_id / "approval.json"


def write_multi_worker_dry_run_approval(authorization: MultiWorkerWorkflowDryRunAuthorization, project_root: str | Path) -> Path:
    path = multi_worker_dry_run_approval_path(project_root, authorization.plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(authorization.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_multi_worker_dry_run_approval(project_root: str | Path, plan_id: str) -> MultiWorkerWorkflowDryRunAuthorization:
    path = multi_worker_dry_run_approval_path(project_root, plan_id)
    if not path.exists():
        raise FileNotFoundError(f"Multi-worker dry-run approval not found for plan_id: {plan_id}")
    return MultiWorkerWorkflowDryRunAuthorization.model_validate_json(path.read_text(encoding="utf-8"))


def build_multi_worker_profile_runner(
    *,
    mode: MultiWorkerProfileRunnerMode | str,
    project_root: str | Path,
    worker_profile: str,
    fake_worker_response_json: str | None = None,
    hermes_run_record_path: str | Path | None = None,
) -> ProfileRunnerLike:
    """Build the selected runner, failing closed before provider/profile calls.

    ``fake`` remains the deterministic provider-free path. ``hermes`` is a real
    profile subprocess seam only when supplied with a persisted, exact provider
    run authorization record; otherwise it raises before execution.
    """

    selected_mode = MultiWorkerProfileRunnerMode(mode)
    if selected_mode == MultiWorkerProfileRunnerMode.FAKE:
        if fake_worker_response_json is None:
            raise MultiWorkerProfileRunnerSelectionError(
                "--fake-worker-response-json is required when --profile-runner=fake"
            )
        return FakeProfileRunner({worker_profile: fake_worker_response_json})

    if hermes_run_record_path is None:
        raise MultiWorkerProfileRunnerSelectionError(
            "--hermes-run-record is required when --profile-runner=hermes"
        )
    record_path = Path(hermes_run_record_path)
    if not record_path.exists():
        raise MultiWorkerProfileRunnerSelectionError(f"Hermes profile run record not found: {record_path}")
    try:
        run_record = AuthorizedProviderRunRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pydantic/json parsing errors fail closed at the selection gate.
        raise MultiWorkerProfileRunnerSelectionError(
            f"Hermes profile run record is invalid: {exc}"
        ) from exc
    if run_record.authorization.provider_or_profile != worker_profile:
        raise MultiWorkerProfileRunnerSelectionError(
            "Hermes profile run record profile does not match selected worker"
        )
    try:
        return HermesProfileSubprocessRunner(run_record=run_record, project_root=project_root)
    except ValueError as exc:
        raise MultiWorkerProfileRunnerSelectionError(str(exc)) from exc


class MultiWorkerWorkflowDryRunReport(FeiyueModel):
    run_id: str
    task_id: str
    plan_id: str
    status: MultiWorkerWorkflowDryRunStatus
    worker_profile: str | None = None
    teacher_profile: str | None = None
    provider_call_count: int = Field(default=0, ge=0)
    reason_codes: list[str]
    dry_run_only: bool = True
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    route_plan_status: str
    routing_apply_evidence_id: str | None = None
    workflow_report: WorkflowExecutionReport | None = None
    dry_run_report: RealProfileWorkflowRunReport | None = None
    teacher_guidance_events: list[dict[str, object]] = Field(default_factory=list)
    retry_performed: bool = False

    @field_validator("run_id", "task_id", "plan_id", "route_plan_status")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("report strings must be non-empty")
        return normalized

    @field_validator("reason_codes")
    @classmethod
    def _required_reasons(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("reason_codes must be non-empty")
        return [str(item).strip() for item in value if str(item).strip()]


class MultiWorkerWorkflowDryRunOrchestrator:
    """Execute an authorized dry-run workflow using a multi-worker route plan."""

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
        authorization: MultiWorkerWorkflowDryRunAuthorization | None,
        run_id: str,
        teacher_escalation_authorization: MultiWorkerTeacherEscalationAuthorization | None = None,
    ) -> MultiWorkerWorkflowDryRunReport:
        project_root_path = Path(project_root)
        block_reasons = _authorization_block_reasons(plan=plan, contract=contract, authorization=authorization)
        if plan.route.status != RouteStatus.SELECTED:
            block_reasons = _dedupe([*block_reasons, "multi_worker_plan_not_selected", *plan.route.reason_codes])
        if block_reasons:
            report = _blocked_report(run_id=run_id, contract=contract, plan=plan, reason_codes=block_reasons)
            self._write_evidence(report, project_root_path)
            return report

        assert authorization is not None
        worker_profile = plan.route.worker_profile_ids[0]
        teacher_profile = _authorized_teacher_profile(
            plan=plan,
            contract=contract,
            worker_profile=worker_profile,
            authorization=teacher_escalation_authorization,
        )
        max_profile_calls = (
            teacher_escalation_authorization.max_profile_calls
            if teacher_profile is not None and teacher_escalation_authorization is not None
            else authorization.max_profile_calls
        )
        dry_run = RealProfileWorkflowRunner(profile_runner=self._profile_runner).run(
            source_repo=source_repo,
            contract=contract,
            project_name=project_name,
            worker_profile=worker_profile,
            teacher_profile=teacher_profile,
            authorization=RealProfileWorkflowAuthorization(
                scopes=_real_profile_scopes(teacher_profile is not None),
                max_profile_calls=max_profile_calls,
                dry_run_only=True,
                allow_real_project=True,
            ),
            evidence_root=project_root_path,
            run_id=run_id,
        )
        missing_teacher_auth = dry_run.status == RealProfileWorkflowStatus.NEEDS_TEACHER and teacher_profile is None
        status = MultiWorkerWorkflowDryRunStatus.BLOCKED if missing_teacher_auth else _map_status(dry_run.status)
        report = MultiWorkerWorkflowDryRunReport(
            run_id=run_id,
            task_id=contract.task_id,
            plan_id=plan.plan_id,
            status=status,
            worker_profile=dry_run.worker_profile,
            teacher_profile=dry_run.teacher_profile,
            provider_call_count=dry_run.provider_call_count,
            reason_codes=_dedupe([
                "multi_worker_plan_authorization_applies",
                "multi_worker_workflow_dry_run_only",
                *plan.reason_codes,
                *(["teacher_escalation_authorization_missing"] if missing_teacher_auth else []),
                *dry_run.reason_codes,
            ]),
            dry_run_only=True,
            promotion_attempted=False,
            global_hermes_config_mutated=False,
            route_plan_status=str(plan.route.status),
            routing_apply_evidence_id=plan.routing_apply_evidence_id,
            workflow_report=dry_run.workflow_report,
            dry_run_report=dry_run,
            teacher_guidance_events=dry_run.teacher_guidance_events,
            retry_performed=dry_run.retry_performed,
        )
        self._write_evidence(report, project_root_path)
        return report

    @staticmethod
    def _write_evidence(report: MultiWorkerWorkflowDryRunReport, project_root: Path) -> Path:
        evidence_dir = project_root / ".hermes" / "multi-worker-workflows" / report.run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        payload = report.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()}
        evidence_path = evidence_dir / "evidence.json"
        evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (evidence_dir / "report.md").write_text(_render_markdown_report(report), encoding="utf-8")
        return evidence_path


def _authorization_block_reasons(
    *,
    plan: MultiWorkerOrchestrationPlan,
    contract: TaskContract,
    authorization: MultiWorkerWorkflowDryRunAuthorization | None,
) -> list[str]:
    if authorization is None:
        return ["missing_multi_worker_workflow_authorization"]
    reasons: list[str] = []
    if authorization.plan_id != plan.plan_id:
        reasons.append("authorization_plan_id_mismatch")
    if authorization.task_id != contract.task_id or authorization.task_id != plan.task_id:
        reasons.append("authorization_task_id_mismatch")
    if authorization.approved_action != "execute_multi_worker_workflow_dry_run":
        reasons.append("authorization_action_mismatch")
    if authorization.worker_profile_ids != plan.route.worker_profile_ids:
        reasons.append("authorization_worker_profile_ids_mismatch")
    if not authorization.allows("multi_worker_workflow_execute"):
        reasons.append("authorization_scope_multi_worker_workflow_execute_missing")
    if not authorization.dry_run_only:
        reasons.append("authorization_must_be_dry_run_only")
    if authorization.max_profile_calls < 1:
        reasons.append("max_profile_calls_would_be_exceeded")
    return reasons


def _blocked_report(
    *,
    run_id: str,
    contract: TaskContract,
    plan: MultiWorkerOrchestrationPlan,
    reason_codes: list[str],
) -> MultiWorkerWorkflowDryRunReport:
    return MultiWorkerWorkflowDryRunReport(
        run_id=run_id,
        task_id=contract.task_id,
        plan_id=plan.plan_id,
        status=MultiWorkerWorkflowDryRunStatus.BLOCKED,
        worker_profile=plan.route.worker_profile_ids[0] if plan.route.worker_profile_ids else None,
        teacher_profile=plan.route.teacher_profile_id,
        provider_call_count=0,
        reason_codes=_dedupe(reason_codes),
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        route_plan_status=str(plan.route.status),
        routing_apply_evidence_id=plan.routing_apply_evidence_id,
    )


def _authorized_teacher_profile(
    *,
    plan: MultiWorkerOrchestrationPlan,
    contract: TaskContract,
    worker_profile: str,
    authorization: MultiWorkerTeacherEscalationAuthorization | None,
) -> str | None:
    teacher_profile = plan.route.teacher_profile_id or _available_teacher_profile(plan)
    if teacher_profile is None or authorization is None:
        return None
    if authorization.plan_id != plan.plan_id:
        return None
    if authorization.task_id != contract.task_id or authorization.task_id != plan.task_id:
        return None
    if authorization.approved_action != "execute_multi_worker_teacher_escalation_retry":
        return None
    if authorization.worker_profile_id != worker_profile or authorization.teacher_profile_id != teacher_profile:
        return None
    if not authorization.dry_run_only or authorization.max_profile_calls < 3:
        return None
    if not authorization.allows("teacher_escalation"):
        return None
    return teacher_profile


def _available_teacher_profile(plan: MultiWorkerOrchestrationPlan) -> str | None:
    value = plan.audit_metadata.get("available_teacher_profile_id")
    return value if isinstance(value, str) and value.strip() else None


def _real_profile_scopes(teacher_escalation_authorized: bool) -> list[str]:
    scopes = ["real_profile_workflow_execute"]
    if teacher_escalation_authorized:
        scopes.append("teacher_escalation")
    return scopes


def _map_status(status: RealProfileWorkflowStatus) -> MultiWorkerWorkflowDryRunStatus:
    if status == RealProfileWorkflowStatus.VERIFIED:
        return MultiWorkerWorkflowDryRunStatus.VERIFIED
    if status == RealProfileWorkflowStatus.NEEDS_TEACHER:
        return MultiWorkerWorkflowDryRunStatus.NEEDS_TEACHER
    return MultiWorkerWorkflowDryRunStatus.BLOCKED


def _render_markdown_report(report: MultiWorkerWorkflowDryRunReport) -> str:
    return "\n".join(
        [
            f"# Multi-worker workflow dry-run: {report.run_id}",
            "",
            f"task_id: {report.task_id}",
            f"plan_id: {report.plan_id}",
            f"status: {report.status}",
            f"worker_profile: {report.worker_profile or 'none'}",
            f"teacher_profile: {report.teacher_profile or 'none'}",
            f"provider_call_count: {report.provider_call_count}",
            f"dry_run_only: {str(report.dry_run_only).lower()}",
            f"promotion_attempted: {str(report.promotion_attempted).lower()}",
            f"global_hermes_config_mutated: {str(report.global_hermes_config_mutated).lower()}",
            f"retry_performed: {str(report.retry_performed).lower()}",
            f"teacher_guidance_events: {len(report.teacher_guidance_events)}",
            "",
            "## Reason codes",
            *[f"- {reason}" for reason in report.reason_codes],
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
