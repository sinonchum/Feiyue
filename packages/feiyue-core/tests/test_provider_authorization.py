from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from feiyue_core.providers.authorization import (
    AuthorizedProviderRunRecord,
    AuthorizedScope,
    RealProviderAuthorization,
    write_provider_run_evidence,
)
from feiyue_core.providers.diagnostics import ProviderFailureKind, classify_provider_failure
from feiyue_core.providers.profile_runner import ProfileRunResult


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


def test_authorization_accepts_exact_allowed_scopes() -> None:
    scopes = {scope.value for scope in AuthorizedScope}

    assert scopes == {
        "real_http_smoke",
        "hermes_profile_subprocess",
        "teacher_escalation",
        "weak_strong_benchmark",
    }
    assert _auth(authorized_scope="hermes_profile_subprocess").authorized_scope is AuthorizedScope.HERMES_PROFILE_SUBPROCESS


@pytest.mark.parametrize(
    "missing_field",
    [
        "approved_by",
        "authorized_scope",
        "provider_or_profile",
        "command",
        "cwd",
        "max_requests",
        "timeout_seconds",
        "budget_ceiling",
        "network_scope",
        "evidence_retention",
        "no_global_config_mutation",
        "approved_at",
    ],
)
def test_authorization_fails_closed_when_approval_checklist_is_missing(missing_field: str) -> None:
    payload = _auth().model_dump()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        RealProviderAuthorization(**payload)


def test_authorization_fails_closed_when_global_config_mutation_not_forbidden() -> None:
    with pytest.raises(ValidationError, match="no_global_config_mutation"):
        _auth(no_global_config_mutation=False)


def test_authorization_rejects_unknown_scope() -> None:
    with pytest.raises(ValidationError):
        _auth(authorized_scope="ungated_live_run")


def test_evidence_writer_persists_redacted_json_under_provider_runs(tmp_path: Path) -> None:
    auth = _auth()
    record = AuthorizedProviderRunRecord(run_id="run-001", authorization=auth, artifacts=("artifact.txt",))
    result = ProfileRunResult(
        stdout="finished password=short",
        stderr="failed token: smalltok",
        exit_code=2,
    )
    diagnostic = classify_provider_failure(result.stderr, exit_code=result.exit_code)

    path = write_provider_run_evidence(
        record,
        result=result,
        diagnostic=diagnostic,
        project_root=tmp_path,
        abort_gate="none",
    )

    assert path == tmp_path / ".hermes" / "provider-runs" / "run-001" / "run-evidence.json"
    data = json.loads(path.read_text())
    assert data["command"] == ["hermes", "run", "--profile", "lane-v-student"]
    assert data["exit_code"] == 2
    assert data["diagnostic_kind"] == ProviderFailureKind.UNKNOWN.value
    assert data["artifacts"] == ["artifact.txt"]
    assert data["abort_gate_triggered"] == "none"
    assert "short" not in json.dumps(data)
    assert "smalltok" not in json.dumps(data)
    assert "[REDACTED]" in data["stdout_redacted"]
    assert "[REDACTED]" in data["stderr_redacted"]
