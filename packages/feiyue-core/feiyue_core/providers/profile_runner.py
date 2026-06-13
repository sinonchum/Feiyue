from __future__ import annotations

import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .authorization import AuthorizedProviderRunRecord, AuthorizedScope, write_provider_run_evidence
from .diagnostics import classify_provider_failure


class ProfileRunRequest(BaseModel):
    """Request to run a named Hermes profile in the Lane V harness.

    The fake runner uses this contract only for deterministic test doubles; it
    never shells out to a real Hermes profile or reads user configuration.
    """

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1)
    role: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("prompt", "role", "profile")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("source_ids")
    @classmethod
    def _non_blank_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("must include at least one source id")
        for source_id in value:
            if not source_id.strip():
                raise ValueError("source ids must be non-empty")
        return value


class ProfileRunResult(BaseModel):
    """Deterministic result of a fake profile run."""

    model_config = ConfigDict(frozen=True)

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class FakeProfileRunner:
    """Profile runner test double backed by canned profile responses.

    This class intentionally performs no subprocess execution and does not touch
    real Hermes configuration. It maps a requested profile name to a canned
    stdout response so higher-level Lane V code can be tested deterministically.
    """

    def __init__(self, responses: Mapping[str, str]) -> None:
        self._responses = dict(responses)

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        response = self._responses.get(request.profile)
        if response is None:
            return ProfileRunResult(
                stdout="",
                stderr=f"profile '{request.profile}' is not configured for FakeProfileRunner",
                exit_code=127,
            )

        return ProfileRunResult(stdout=response, stderr="", exit_code=0)


SubprocessRunner = Callable[..., subprocess.CompletedProcess[str]]


_BLOCKED_HERMES_MUTATIONS: tuple[tuple[str, ...], ...] = (
    ("hermes", "config", "set"),
    ("hermes", "model"),
    ("hermes", "profile", "set"),
    ("hermes", "profiles", "set"),
)


def _starts_with(command: Sequence[str], prefix: Sequence[str]) -> bool:
    return tuple(command[: len(prefix)]) == tuple(prefix)


def _is_blocked_global_config_mutation(command: Sequence[str]) -> bool:
    return any(_starts_with(command, prefix) for prefix in _BLOCKED_HERMES_MUTATIONS)


class HermesProfileSubprocessRunner:
    """Authorization-gated runner for a real Hermes profile subprocess.

    The runner executes only the exact command recorded in the human approval
    record and writes redacted evidence for success, failure, and abort gates.
    Tests should inject ``subprocess_runner``; production defaults to
    ``subprocess.run`` but remains fail-closed without a valid authorization.
    """

    def __init__(
        self,
        *,
        run_record: AuthorizedProviderRunRecord,
        project_root: str | Path,
        subprocess_runner: SubprocessRunner | None = None,
    ) -> None:
        if run_record is None:
            raise ValueError("authorization run record is required")
        authorization = run_record.authorization
        if authorization.authorized_scope is not AuthorizedScope.HERMES_PROFILE_SUBPROCESS:
            raise ValueError("authorization scope must be hermes_profile_subprocess")
        if _is_blocked_global_config_mutation(authorization.command):
            raise ValueError("global Hermes config mutation command is blocked")
        self._run_record = run_record
        self._project_root = Path(project_root)
        self._subprocess_runner = subprocess_runner or subprocess.run

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        authorization = self._run_record.authorization
        started_at = datetime.now(UTC)

        if request.profile != authorization.provider_or_profile:
            result = ProfileRunResult(
                stdout="",
                stderr=(
                    f"profile '{request.profile}' is not authorized for run "
                    f"'{self._run_record.run_id}'"
                ),
                exit_code=126,
            )
            diagnostic = classify_provider_failure(result.stderr, result.exit_code)
            write_provider_run_evidence(
                self._run_record,
                result=result,
                diagnostic=diagnostic,
                project_root=self._project_root,
                started_at=started_at,
                ended_at=datetime.now(UTC),
                abort_gate="profile_mismatch",
            )
            return result

        command = list(authorization.command)
        try:
            completed = self._subprocess_runner(
                command,
                cwd=authorization.cwd,
                timeout=authorization.timeout_seconds,
                capture_output=True,
                text=True,
                check=False,
            )
            result = ProfileRunResult(
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                exit_code=int(completed.returncode),
            )
        except subprocess.TimeoutExpired as exc:
            result = ProfileRunResult(
                stdout=str(exc.output or ""),
                stderr=str(exc.stderr or "provider subprocess timed out"),
                exit_code=124,
                timed_out=True,
            )

        diagnostic = None
        if result.exit_code != 0 or result.timed_out:
            diagnostic = classify_provider_failure(
                result.stderr,
                exit_code=result.exit_code,
                timed_out=result.timed_out,
            )
        write_provider_run_evidence(
            self._run_record,
            result=result,
            diagnostic=diagnostic,
            project_root=self._project_root,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            abort_gate=None,
        )
        return result
