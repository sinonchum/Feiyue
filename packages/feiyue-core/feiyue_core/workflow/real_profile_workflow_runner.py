from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from feiyue_core.providers.diagnostics import redact_secrets
from feiyue_core.providers.profile_runner import ProfileRunRequest
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.execution import ToyWorkflowExecutor, WorkflowExecutionReport, WorkflowExecutionStatus
from feiyue_core.workflow.profile_worker_bridge import ProfileRunnerLike, _parse_candidate_writes
from feiyue_core.workflow.task_contract import TaskContract


class RealProfileWorkflowStatus(StrEnum):
    VERIFIED = "verified"
    NEEDS_TEACHER = "needs_teacher"
    BLOCKED = "blocked"


class RealProfileWorkflowAuthorization(FeiyueModel):
    scopes: list[str]
    max_profile_calls: int = Field(default=1, ge=0)
    dry_run_only: bool = True
    allow_real_project: bool = False

    @field_validator("scopes")
    @classmethod
    def _non_empty_scopes(cls, value: list[str]) -> list[str]:
        normalized = [scope.strip() for scope in value]
        if not normalized or any(not scope for scope in normalized):
            raise ValueError("scopes must contain non-empty values")
        return normalized

    def allows(self, scope: str) -> bool:
        return scope in self.scopes


class RealProfileWorkflowRunReport(FeiyueModel):
    run_id: str
    task_id: str
    status: RealProfileWorkflowStatus
    worker_profile: str
    teacher_profile: str | None = None
    provider_call_count: int = Field(ge=0)
    reason_codes: list[str]
    dry_run_only: bool
    promotion_attempted: bool = False
    source_repo_clean: bool
    workflow_report: WorkflowExecutionReport | None = None
    teacher_guidance_redacted: str | None = None
    teacher_guidance_events: list[dict[str, object]] = Field(default_factory=list)
    retry_performed: bool = False
    stdout_redacted: list[str] = Field(default_factory=list)
    stderr_redacted: list[str] = Field(default_factory=list)

    @field_validator("run_id", "task_id", "worker_profile")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value


class RealProfileWorkflowRunner:
    def __init__(self, *, profile_runner: ProfileRunnerLike, workflow_executor: ToyWorkflowExecutor | None = None) -> None:
        self._profile_runner = profile_runner
        self._workflow_executor = workflow_executor or ToyWorkflowExecutor()

    def run(
        self,
        *,
        source_repo: str | Path,
        contract: TaskContract,
        project_name: str,
        worker_profile: str,
        teacher_profile: str | None,
        authorization: RealProfileWorkflowAuthorization | None,
        evidence_root: str | Path,
        run_id: str,
    ) -> RealProfileWorkflowRunReport:
        source_path = Path(source_repo)
        if authorization is None:
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, 0, ["missing_real_profile_workflow_authorization"], True, source_path)
            self._write_evidence(report, evidence_root)
            return report
        if not authorization.allows("real_profile_workflow_execute"):
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, 0, ["authorization_scope_real_profile_workflow_execute_missing"], authorization.dry_run_only, source_path)
            self._write_evidence(report, evidence_root)
            return report
        if authorization.max_profile_calls < 1:
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, 0, ["max_profile_calls_would_be_exceeded"], authorization.dry_run_only, source_path)
            self._write_evidence(report, evidence_root)
            return report

        stdout_redacted: list[str] = []
        stderr_redacted: list[str] = []
        provider_call_count = 0
        initial = self._profile_runner.run(
            ProfileRunRequest(
                prompt=_render_worker_prompt(contract, guidance=None),
                role="worker",
                profile=worker_profile,
                source_ids=(f"task:{contract.task_id}", "real-profile-workflow-runner", "initial"),
            )
        )
        provider_call_count += 1
        stdout_redacted.append(redact_secrets(initial.stdout))
        stderr_redacted.append(redact_secrets(initial.stderr))
        if initial.exit_code != 0 or initial.timed_out:
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["worker_profile_failed"], authorization.dry_run_only, source_path, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report
        try:
            initial_writes = _parse_candidate_writes(initial.stdout)
        except ValueError:
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["worker_output_parse_failed"], authorization.dry_run_only, source_path, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report

        first_report = self._workflow_executor.execute(
            source_repo=source_path,
            contract=contract,
            candidate_writes=initial_writes,
            project_name=project_name,
        )
        if first_report.status == WorkflowExecutionStatus.VERIFIED:
            report = self._report(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["real_profile_workflow_execute_authorized", "dry_run_no_promotion"], authorization.dry_run_only, source_path, first_report, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report

        if teacher_profile is None or not authorization.allows("teacher_escalation"):
            report = self._report(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["needs_teacher_without_authorized_teacher_escalation", "dry_run_no_promotion"], authorization.dry_run_only, source_path, first_report, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report
        if authorization.max_profile_calls < 3:
            report = self._report(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["teacher_retry_budget_exceeded", "dry_run_no_promotion"], authorization.dry_run_only, source_path, first_report, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report

        teacher = self._profile_runner.run(
            ProfileRunRequest(
                prompt=_render_teacher_prompt(contract, first_report),
                role="teacher",
                profile=teacher_profile,
                source_ids=(f"task:{contract.task_id}", "real-profile-workflow-runner", "teacher"),
            )
        )
        provider_call_count += 1
        stdout_redacted.append(redact_secrets(teacher.stdout))
        stderr_redacted.append(redact_secrets(teacher.stderr))
        if teacher.exit_code != 0 or teacher.timed_out:
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["teacher_profile_failed"], authorization.dry_run_only, source_path, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report
        guidance = _parse_teacher_guidance(teacher.stdout)

        retry = self._profile_runner.run(
            ProfileRunRequest(
                prompt=_render_worker_prompt(contract, guidance=guidance),
                role="worker",
                profile=worker_profile,
                source_ids=(f"task:{contract.task_id}", "real-profile-workflow-runner", "retry"),
            )
        )
        provider_call_count += 1
        stdout_redacted.append(redact_secrets(retry.stdout))
        stderr_redacted.append(redact_secrets(retry.stderr))
        if retry.exit_code != 0 or retry.timed_out:
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["retry_worker_profile_failed"], authorization.dry_run_only, source_path, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report
        try:
            retry_writes = _parse_candidate_writes(retry.stdout)
        except ValueError:
            report = self._blocked(run_id, contract, worker_profile, teacher_profile, provider_call_count, ["retry_worker_output_parse_failed"], authorization.dry_run_only, source_path, stdout_redacted, stderr_redacted)
            self._write_evidence(report, evidence_root)
            return report

        final_report = self._workflow_executor.execute_with_teacher_retry(
            source_repo=source_path,
            contract=contract,
            initial_writes=initial_writes,
            teacher_guidance=guidance,
            revised_writes=retry_writes,
            project_name=project_name,
            max_attempts=2,
        )
        report = self._report(
            run_id,
            contract,
            worker_profile,
            teacher_profile,
            provider_call_count,
            ["real_profile_workflow_execute_authorized", "teacher_escalation_authorized", "dry_run_no_promotion"],
            authorization.dry_run_only,
            source_path,
            final_report,
            stdout_redacted,
            stderr_redacted,
            teacher_guidance_redacted=redact_secrets(guidance),
        )
        self._write_evidence(report, evidence_root)
        return report

    @staticmethod
    def _source_repo_clean(source_path: Path) -> bool:
        import subprocess

        completed = subprocess.run(["git", "status", "--porcelain"], cwd=source_path, text=True, capture_output=True, check=False)
        return completed.returncode == 0 and completed.stdout == ""

    def _report(self, run_id: str, contract: TaskContract, worker_profile: str, teacher_profile: str | None, provider_call_count: int, reason_codes: list[str], dry_run_only: bool, source_path: Path, workflow_report: WorkflowExecutionReport, stdout_redacted: list[str], stderr_redacted: list[str], teacher_guidance_redacted: str | None = None) -> RealProfileWorkflowRunReport:
        status = RealProfileWorkflowStatus.VERIFIED if workflow_report.status == WorkflowExecutionStatus.VERIFIED else RealProfileWorkflowStatus.NEEDS_TEACHER if workflow_report.status == WorkflowExecutionStatus.NEEDS_TEACHER else RealProfileWorkflowStatus.BLOCKED
        return RealProfileWorkflowRunReport(
            run_id=run_id,
            task_id=contract.task_id,
            status=status,
            worker_profile=worker_profile,
            teacher_profile=teacher_profile,
            provider_call_count=provider_call_count,
            reason_codes=reason_codes,
            dry_run_only=dry_run_only,
            promotion_attempted=False,
            source_repo_clean=self._source_repo_clean(source_path),
            workflow_report=workflow_report,
            teacher_guidance_redacted=teacher_guidance_redacted,
            teacher_guidance_events=[event.model_dump(mode="json") for event in workflow_report.teacher_guidance_events],
            retry_performed=workflow_report.retry_performed,
            stdout_redacted=stdout_redacted,
            stderr_redacted=stderr_redacted,
        )

    def _blocked(self, run_id: str, contract: TaskContract, worker_profile: str, teacher_profile: str | None, provider_call_count: int, reason_codes: list[str], dry_run_only: bool, source_path: Path, stdout_redacted: list[str] | None = None, stderr_redacted: list[str] | None = None) -> RealProfileWorkflowRunReport:
        return RealProfileWorkflowRunReport(
            run_id=run_id,
            task_id=contract.task_id,
            status=RealProfileWorkflowStatus.BLOCKED,
            worker_profile=worker_profile,
            teacher_profile=teacher_profile,
            provider_call_count=provider_call_count,
            reason_codes=reason_codes,
            dry_run_only=dry_run_only,
            promotion_attempted=False,
            source_repo_clean=self._source_repo_clean(source_path),
            stdout_redacted=stdout_redacted or [],
            stderr_redacted=stderr_redacted or [],
        )

    @staticmethod
    def _write_evidence(report: RealProfileWorkflowRunReport, evidence_root: str | Path) -> Path:
        evidence_dir = Path(evidence_root) / ".hermes" / "workflow-smokes" / report.run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        payload = report.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()}
        evidence_path = evidence_dir / "evidence.json"
        evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (evidence_dir / "report.md").write_text(_render_markdown_report(report), encoding="utf-8")
        return evidence_path


def _parse_teacher_guidance(stdout: str) -> str:
    try:
        payload = json.loads(stdout)
        if isinstance(payload, dict) and isinstance(payload.get("guidance"), str) and payload["guidance"].strip():
            return payload["guidance"].strip()
    except json.JSONDecodeError:
        pass
    return stdout.strip()


def _render_worker_prompt(contract: TaskContract, *, guidance: str | None) -> str:
    guidance_section = f"\nTeacher guidance: {guidance}" if guidance else ""
    return contract.render_markdown() + guidance_section + "\nReturn JSON only with writes."


def _render_teacher_prompt(contract: TaskContract, report: WorkflowExecutionReport) -> str:
    dossier = report.bug_dossier
    failure = dossier.error_excerpt if dossier is not None else "No bug dossier available."
    return contract.render_markdown() + "\nVerifier failure excerpt:\n" + failure + "\nReturn JSON only: {\"guidance\": \"...\"}."


def _render_markdown_report(report: RealProfileWorkflowRunReport) -> str:
    workflow_status = report.workflow_report.status if report.workflow_report is not None else None
    verification_passed = report.workflow_report.verification_passed if report.workflow_report is not None else None
    return "\n".join(
        [
            "# Real Profile Workflow Run",
            "",
            f"- run_id: {report.run_id}",
            f"- task_id: {report.task_id}",
            f"- status: {report.status}",
            f"- worker_profile: {report.worker_profile}",
            f"- teacher_profile: {report.teacher_profile}",
            f"- provider_call_count: {report.provider_call_count}",
            f"- dry_run_only: {report.dry_run_only}",
            f"- promotion_attempted: {report.promotion_attempted}",
            f"- source_repo_clean: {report.source_repo_clean}",
            f"- workflow_status: {workflow_status}",
            f"- verification_passed: {verification_passed}",
            f"- reason_codes: {', '.join(report.reason_codes)}",
            "",
        ]
    )
