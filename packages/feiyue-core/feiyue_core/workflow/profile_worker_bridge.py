"""Bridge real/fake Hermes profile runner output into the M11 workflow executor.

This module is intentionally fake-first and injection-based: it does not shell out,
read credentials, or mutate Hermes configuration. Callers provide a ProfileRunner-
like dependency, and the bridge parses the profile stdout into deterministic
``CandidateFileWrite`` objects before delegating all file mutation and verifier
work to ``ToyWorkflowExecutor`` sandbox logic.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import Field, field_validator

from feiyue_core.providers.diagnostics import redact_secrets
from feiyue_core.providers.profile_runner import ProfileRunRequest, ProfileRunResult
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.execution import CandidateFileWrite, ToyWorkflowExecutor, WorkflowExecutionReport, WorkflowExecutionStatus
from feiyue_core.workflow.task_contract import TaskContract


class ProfileRunnerLike(Protocol):
    """Minimal injected runner contract for worker profile execution."""

    def run(self, request: ProfileRunRequest) -> ProfileRunResult: ...


class ProfileWorkflowBridgeStatus(StrEnum):
    """High-level bridge outcome before/after workflow execution."""

    VERIFIED = "verified"
    NEEDS_TEACHER = "needs_teacher"
    BLOCKED = "blocked"


class ProfileWorkflowBridgeAuthorization(FeiyueModel):
    """Exact authorization envelope for profile-backed workflow execution."""

    scopes: list[str]
    max_profile_calls: int = Field(default=1, ge=0)

    @field_validator("scopes")
    @classmethod
    def _validate_scopes(cls, value: list[str]) -> list[str]:
        normalized = [scope.strip() for scope in value]
        if not normalized or any(not scope for scope in normalized):
            raise ValueError("scopes must contain non-empty values")
        return normalized

    def allows(self, scope: str) -> bool:
        return scope in self.scopes


class ProfileWorkflowBridgeReport(FeiyueModel):
    """Auditable report for the profile-runner-to-workflow bridge."""

    task_id: str
    status: ProfileWorkflowBridgeStatus
    worker_profile: str
    provider_call_count: int = Field(ge=0)
    reason_codes: list[str]
    workflow_report: WorkflowExecutionReport | None = None
    stdout_redacted: str = ""
    stderr_redacted: str = ""

    @field_validator("task_id", "worker_profile")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, value: list[str]) -> list[str]:
        normalized = [reason.strip() for reason in value]
        if not normalized or any(not reason for reason in normalized):
            raise ValueError("reason_codes must contain non-empty values")
        return normalized


class ProfileWorkflowBridge:
    """Run a worker profile once, parse candidate writes, and verify in sandbox."""

    def __init__(
        self,
        *,
        profile_runner: ProfileRunnerLike,
        workflow_executor: ToyWorkflowExecutor | None = None,
    ) -> None:
        self._profile_runner = profile_runner
        self._workflow_executor = workflow_executor or ToyWorkflowExecutor()

    def execute(
        self,
        *,
        source_repo: str | Path,
        contract: TaskContract,
        project_name: str,
        worker_profile: str,
        authorization: ProfileWorkflowBridgeAuthorization | None,
    ) -> ProfileWorkflowBridgeReport:
        worker_profile = _non_empty(worker_profile, "worker_profile")
        if authorization is None:
            return self._blocked(
                contract=contract,
                worker_profile=worker_profile,
                provider_call_count=0,
                reason_codes=["missing_profile_workflow_execute_authorization"],
            )
        if not authorization.allows("profile_workflow_execute"):
            return self._blocked(
                contract=contract,
                worker_profile=worker_profile,
                provider_call_count=0,
                reason_codes=["authorization_scope_profile_workflow_execute_missing"],
            )
        if authorization.max_profile_calls < 1:
            return self._blocked(
                contract=contract,
                worker_profile=worker_profile,
                provider_call_count=0,
                reason_codes=["max_profile_calls_would_be_exceeded"],
            )

        result = self._profile_runner.run(
            ProfileRunRequest(
                prompt=_render_worker_prompt(contract),
                role="worker",
                profile=worker_profile,
                source_ids=(f"task:{contract.task_id}", "profile-workflow-bridge"),
            )
        )
        stdout_redacted = redact_secrets(result.stdout)
        stderr_redacted = redact_secrets(result.stderr)
        if result.exit_code != 0 or result.timed_out:
            return self._blocked(
                contract=contract,
                worker_profile=worker_profile,
                provider_call_count=1,
                reason_codes=["profile_runner_failed"],
                stdout_redacted=stdout_redacted,
                stderr_redacted=stderr_redacted,
            )

        try:
            candidate_writes = _parse_candidate_writes(result.stdout)
        except ValueError:
            return self._blocked(
                contract=contract,
                worker_profile=worker_profile,
                provider_call_count=1,
                reason_codes=["profile_output_parse_failed"],
                stdout_redacted=stdout_redacted,
                stderr_redacted=stderr_redacted,
            )

        workflow_report = self._workflow_executor.execute(
            source_repo=source_repo,
            contract=contract,
            candidate_writes=candidate_writes,
            project_name=project_name,
        )
        if workflow_report.status == WorkflowExecutionStatus.VERIFIED:
            status = ProfileWorkflowBridgeStatus.VERIFIED
        elif workflow_report.status == WorkflowExecutionStatus.NEEDS_TEACHER:
            status = ProfileWorkflowBridgeStatus.NEEDS_TEACHER
        else:
            status = ProfileWorkflowBridgeStatus.BLOCKED
        return ProfileWorkflowBridgeReport(
            task_id=contract.task_id,
            status=status,
            worker_profile=worker_profile,
            provider_call_count=1,
            reason_codes=["profile_workflow_execute_authorized", "profile_runner_injected"],
            workflow_report=workflow_report,
            stdout_redacted=stdout_redacted,
            stderr_redacted=stderr_redacted,
        )

    @staticmethod
    def _blocked(
        *,
        contract: TaskContract,
        worker_profile: str,
        provider_call_count: int,
        reason_codes: list[str],
        stdout_redacted: str = "",
        stderr_redacted: str = "",
    ) -> ProfileWorkflowBridgeReport:
        return ProfileWorkflowBridgeReport(
            task_id=contract.task_id,
            status=ProfileWorkflowBridgeStatus.BLOCKED,
            worker_profile=worker_profile,
            provider_call_count=provider_call_count,
            reason_codes=reason_codes,
            stdout_redacted=stdout_redacted,
            stderr_redacted=stderr_redacted,
        )


def _render_worker_prompt(contract: TaskContract) -> str:
    files = ", ".join(contract.files_to_modify) if contract.files_to_modify else "contract-defined files only"
    commands = "; ".join(contract.verification_commands) if contract.verification_commands else "no verifier configured"
    return (
        "Produce JSON only with shape {\"writes\":[{\"path\":str,\"content\":str}]}.\n"
        f"Task ID: {contract.task_id}\n"
        f"Title: {contract.title}\n"
        f"Scope: {contract.scope}\n"
        f"Files to modify: {files}\n"
        f"Verification commands: {commands}\n"
        "Do not include markdown fences or commentary."
    )


def _parse_candidate_writes(stdout: str) -> list[CandidateFileWrite]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("profile output must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("profile output must be a JSON object")
    raw_writes = payload.get("writes")
    if not isinstance(raw_writes, list) or not raw_writes:
        raise ValueError("profile output must include non-empty writes")
    writes: list[CandidateFileWrite] = []
    for raw_write in raw_writes:
        if not isinstance(raw_write, dict):
            raise ValueError("each write must be an object")
        path = raw_write.get("path")
        content = raw_write.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            raise ValueError("each write must include string path and content")
        writes.append(CandidateFileWrite(path=path, content=content))
    return writes


def _non_empty(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be non-empty")
    return stripped
