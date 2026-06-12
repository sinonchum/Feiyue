from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .diagnostics import ProviderDiagnostic, classify_provider_failure, redact_secrets
from .profile_runner import ProfileRunRequest, ProfileRunResult


class ProfileRunner(Protocol):
    """Minimal runner boundary used by provider integration smoke tests."""

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        """Run a profile request and return the raw process-like result."""
        ...


@dataclass(frozen=True)
class ProfileRunOutcome:
    """Combined raw profile result and optional diagnostic for failures."""

    result: ProfileRunResult
    diagnostic: ProviderDiagnostic | None


def run_profile_with_diagnostic(
    runner: ProfileRunner,
    request: ProfileRunRequest,
) -> ProfileRunOutcome:
    """Run a profile through the safe M10 boundary and classify failures.

    The integration boundary remains provider-free: it delegates execution to the
    supplied runner, never reads Hermes configuration, and never invokes a real
    subprocess. Failure diagnostics include the redacted prompt plus stderr so a
    fallback model can see useful context without leaking credentials.
    """
    result = runner.run(request)
    if result.exit_code == 0 and not result.timed_out:
        return ProfileRunOutcome(result=result, diagnostic=None)

    diagnostic_input = "\n".join(
        part
        for part in (
            result.stderr,
            f"prompt: {redact_secrets(request.prompt)}",
            f"profile: {request.profile}",
            f"role: {request.role}",
        )
        if part
    )
    return ProfileRunOutcome(
        result=result,
        diagnostic=classify_provider_failure(
            diagnostic_input,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
        ),
    )
