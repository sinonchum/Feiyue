from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .diagnostics import ProviderDiagnostic, redact_secrets

if TYPE_CHECKING:
    from .profile_runner import ProfileRunResult


class AuthorizedScope(StrEnum):
    REAL_HTTP_SMOKE = "real_http_smoke"
    HERMES_PROFILE_SUBPROCESS = "hermes_profile_subprocess"
    TEACHER_ESCALATION = "teacher_escalation"
    WEAK_STRONG_BENCHMARK = "weak_strong_benchmark"


class RealProviderAuthorization(BaseModel):
    """Human approval checklist for an otherwise forbidden real-provider surface."""

    model_config = ConfigDict(frozen=True)

    approved_by: str = Field(min_length=1)
    authorized_scope: AuthorizedScope
    provider_or_profile: str = Field(min_length=1)
    command: tuple[str, ...] = Field(min_length=1)
    cwd: str = Field(min_length=1)
    max_requests: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    budget_ceiling: str = Field(min_length=1)
    network_scope: str = Field(min_length=1)
    evidence_retention: str = Field(min_length=1)
    no_global_config_mutation: bool = Field(...)
    approved_at: datetime

    @field_validator(
        "approved_by",
        "provider_or_profile",
        "cwd",
        "budget_ceiling",
        "network_scope",
        "evidence_retention",
    )
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("command")
    @classmethod
    def _non_blank_command(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("command must be non-empty")
        for part in value:
            if not part.strip():
                raise ValueError("command parts must be non-empty")
        return value

    @model_validator(mode="after")
    def _fail_closed_contracts(self) -> RealProviderAuthorization:
        if self.no_global_config_mutation is not True:
            raise ValueError("no_global_config_mutation must be True")
        if self.provider_or_profile not in self.command:
            raise ValueError("command must name the exact provider_or_profile")
        return self


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class AuthorizedProviderRunRecord(BaseModel):
    """Concrete authorized run record used to bind execution and evidence."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    authorization: RealProviderAuthorization
    artifacts: tuple[str, ...] = ()
    commit_sha: str | None = None

    @field_validator("run_id")
    @classmethod
    def _safe_run_id(cls, value: str) -> str:
        if not _RUN_ID_RE.fullmatch(value):
            raise ValueError("run_id may contain only letters, digits, dot, underscore, and dash")
        return value


class ProviderRunEvidence(BaseModel):
    """Secret-free JSON evidence for an authorized provider/profile run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    commit_sha: str | None = None
    approved_by: str
    authorized_scope: AuthorizedScope
    provider_or_profile: str
    command: tuple[str, ...]
    cwd: str
    started_at: datetime
    ended_at: datetime
    exit_code: int | None
    diagnostic_kind: str | None
    stdout_redacted: str
    stderr_redacted: str
    artifacts: tuple[str, ...]
    abort_gate_triggered: str | None = None


def _redacted_summary(text: str, *, limit: int = 4000) -> str:
    redacted = redact_secrets(text)
    if len(redacted) <= limit:
        return redacted
    return f"{redacted[:limit]}\n[truncated {len(redacted) - limit} chars]"


def build_provider_run_evidence(
    record: AuthorizedProviderRunRecord,
    *,
    result: ProfileRunResult,
    diagnostic: ProviderDiagnostic | None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    abort_gate: str | None = None,
) -> ProviderRunEvidence:
    now = datetime.now(UTC)
    authorization = record.authorization
    return ProviderRunEvidence(
        run_id=record.run_id,
        commit_sha=record.commit_sha,
        approved_by=authorization.approved_by,
        authorized_scope=authorization.authorized_scope,
        provider_or_profile=authorization.provider_or_profile,
        command=authorization.command,
        cwd=authorization.cwd,
        started_at=started_at or now,
        ended_at=ended_at or now,
        exit_code=result.exit_code,
        diagnostic_kind=diagnostic.kind.value if diagnostic is not None else None,
        stdout_redacted=_redacted_summary(result.stdout),
        stderr_redacted=_redacted_summary(result.stderr),
        artifacts=record.artifacts,
        abort_gate_triggered=abort_gate,
    )


def write_provider_run_evidence(
    record: AuthorizedProviderRunRecord,
    *,
    result: ProfileRunResult,
    diagnostic: ProviderDiagnostic | None,
    project_root: str | Path,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    abort_gate: str | None = None,
) -> Path:
    """Write redacted run evidence under .hermes/provider-runs/<run_id>."""

    evidence = build_provider_run_evidence(
        record,
        result=result,
        diagnostic=diagnostic,
        started_at=started_at,
        ended_at=ended_at,
        abort_gate=abort_gate,
    )
    evidence_dir = Path(project_root) / ".hermes" / "provider-runs" / record.run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "run-evidence.json"
    payload: dict[str, Any] = evidence.model_dump(mode="json")
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return evidence_path
