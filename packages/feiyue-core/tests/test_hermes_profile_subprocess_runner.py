from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from feiyue_core.providers import ProfileRunRequest, ProviderFailureKind
from feiyue_core.providers.authorization import (
    AuthorizedProviderRunRecord,
    AuthorizedScope,
    RealProviderAuthorization,
)
from feiyue_core.providers.profile_runner import HermesProfileSubprocessRunner


def _auth(**overrides: object) -> RealProviderAuthorization:
    payload: dict[str, object] = {
        "approved_by": "owner-name",
        "authorized_scope": AuthorizedScope.HERMES_PROFILE_SUBPROCESS,
        "provider_or_profile": "lane-v-student",
        "command": ["hermes", "run", "--profile", "lane-v-student"],
        "cwd": "/tmp/hermes-smoke",
        "max_requests": 1,
        "timeout_seconds": 5,
        "budget_ceiling": "0.01 USD",
        "network_scope": "operator-approved provider endpoint only",
        "evidence_retention": ".hermes/provider-runs retained locally",
        "no_global_config_mutation": True,
        "approved_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    payload.update(overrides)
    return RealProviderAuthorization(**payload)


def _request(profile: str = "lane-v-student") -> ProfileRunRequest:
    return ProfileRunRequest(
        prompt="safe prompt",
        role="student",
        profile=profile,
        source_ids=("trace-001",),
    )


class FakeCompletedRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, command, **kwargs):
        self.calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="ok password=short",
            stderr="",
        )


def test_hermes_profile_subprocess_runner_requires_authorization(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="authorization"):
        HermesProfileSubprocessRunner(run_record=None, project_root=tmp_path)  # type: ignore[arg-type]


def test_hermes_profile_subprocess_runner_rejects_wrong_scope(tmp_path: Path) -> None:
    auth = _auth(authorized_scope=AuthorizedScope.REAL_HTTP_SMOKE)
    record = AuthorizedProviderRunRecord(run_id="run-wrong-scope", authorization=auth)

    with pytest.raises(ValueError, match="hermes_profile_subprocess"):
        HermesProfileSubprocessRunner(run_record=record, project_root=tmp_path)


def test_hermes_profile_subprocess_runner_executes_exact_authorized_command_with_fake_subprocess(tmp_path: Path) -> None:
    fake_run = FakeCompletedRunner()
    record = AuthorizedProviderRunRecord(run_id="run-ok", authorization=_auth())
    runner = HermesProfileSubprocessRunner(
        run_record=record,
        project_root=tmp_path,
        subprocess_runner=fake_run,
    )

    result = runner.run(_request())

    assert result.exit_code == 0
    assert result.stdout == "ok password=short"
    assert fake_run.calls == [
        {
            "command": ["hermes", "run", "--profile", "lane-v-student"],
            "cwd": "/tmp/hermes-smoke",
            "timeout": 5,
            "capture_output": True,
            "text": True,
            "check": False,
        }
    ]
    evidence = (tmp_path / ".hermes" / "provider-runs" / "run-ok" / "run-evidence.json").read_text()
    assert "short" not in evidence
    assert "[REDACTED]" in evidence


def test_hermes_profile_subprocess_runner_blocks_profile_mismatch_without_subprocess(tmp_path: Path) -> None:
    fake_run = FakeCompletedRunner()
    record = AuthorizedProviderRunRecord(run_id="run-profile-mismatch", authorization=_auth())
    runner = HermesProfileSubprocessRunner(run_record=record, project_root=tmp_path, subprocess_runner=fake_run)

    result = runner.run(_request(profile="other-profile"))

    assert result.exit_code == 126
    assert "not authorized" in result.stderr
    assert fake_run.calls == []


def test_hermes_profile_subprocess_runner_classifies_timeout_and_writes_evidence(tmp_path: Path) -> None:
    def timeout_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs["timeout"], output="partial", stderr="timeout token=tok")

    record = AuthorizedProviderRunRecord(run_id="run-timeout", authorization=_auth(timeout_seconds=1))
    runner = HermesProfileSubprocessRunner(run_record=record, project_root=tmp_path, subprocess_runner=timeout_runner)

    result = runner.run(_request())

    assert result.exit_code == 124
    assert result.timed_out is True
    evidence = (tmp_path / ".hermes" / "provider-runs" / "run-timeout" / "run-evidence.json").read_text()
    assert ProviderFailureKind.TIMEOUT.value in evidence
    assert "token=tok" not in evidence
    assert "[REDACTED]" in evidence


def test_hermes_profile_subprocess_runner_blocks_global_config_mutation_command(tmp_path: Path) -> None:
    auth = _auth(
        provider_or_profile="something",
        command=["hermes", "config", "set", "model", "something"],
    )
    record = AuthorizedProviderRunRecord(run_id="run-blocked", authorization=auth)

    with pytest.raises(ValueError, match="global Hermes config mutation"):
        HermesProfileSubprocessRunner(run_record=record, project_root=tmp_path, subprocess_runner=FakeCompletedRunner())


def test_hermes_profile_subprocess_runner_requires_exact_profile_in_authorized_command() -> None:
    with pytest.raises(ValidationError):
        _auth(command=["hermes", "run", "--profile", "other-profile"])
