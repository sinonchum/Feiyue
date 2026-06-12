from feiyue_core.providers import (
    FakeProfileRunner,
    ProfileRunRequest,
    ProviderFailureKind,
    run_profile_with_diagnostic,
)


def test_profile_runner_integration_returns_result_without_diagnostic_for_success() -> None:
    runner = FakeProfileRunner({"student-profile": "candidate patch"})
    request = ProfileRunRequest(
        prompt="Generate a candidate",
        role="student",
        profile="student-profile",
        source_ids=("task-001",),
    )

    outcome = run_profile_with_diagnostic(runner, request)

    assert outcome.result.stdout == "candidate patch"
    assert outcome.result.stderr == ""
    assert outcome.result.exit_code == 0
    assert outcome.diagnostic is None


def test_profile_runner_integration_classifies_and_redacts_failed_profile_run() -> None:
    runner = FakeProfileRunner({})
    request = ProfileRunRequest(
        prompt="Generate a candidate with api_key=key1",
        role="fallback",
        profile="missing-profile",
        source_ids=("trace-001",),
    )

    outcome = run_profile_with_diagnostic(runner, request)

    assert outcome.result.exit_code == 127
    assert outcome.diagnostic is not None
    assert outcome.diagnostic.kind == ProviderFailureKind.UNKNOWN
    assert outcome.diagnostic.exit_code == 127
    assert "missing-profile" in outcome.diagnostic.redacted_stderr
    assert "key1" not in outcome.diagnostic.redacted_stderr
    assert "[REDACTED]" in outcome.diagnostic.redacted_stderr


def test_profile_runner_integration_preserves_timeout_diagnostic_priority() -> None:
    class TimeoutRunner:
        def run(self, request: ProfileRunRequest):
            from feiyue_core.providers import ProfileRunResult

            return ProfileRunResult(
                stdout="",
                stderr="401 unauthorized with token: tok2",
                exit_code=124,
                timed_out=True,
            )

    request = ProfileRunRequest(
        prompt="Generate candidate",
        role="student",
        profile="timeout-profile",
        source_ids=("trace-002",),
    )

    outcome = run_profile_with_diagnostic(TimeoutRunner(), request)

    assert outcome.diagnostic is not None
    assert outcome.diagnostic.kind == ProviderFailureKind.TIMEOUT
    assert outcome.diagnostic.timed_out is True
    assert "tok2" not in outcome.diagnostic.redacted_stderr
