from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .base import REDACTED


class ProviderFailureKind(StrEnum):
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderDiagnostic:
    kind: ProviderFailureKind
    message: str
    redacted_stderr: str
    exit_code: int | None
    timed_out: bool = False


_BEARER_PATTERN = re.compile(
    r"(?P<prefix>\bAuthorization\s*:\s*Bearer\s+)(?P<secret>[^\s,;]+)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<prefix>\b(?:api[_-]?key|token|password)\b\s*(?:=|:)\s*)(?P<secret>[^\s,;]+)",
    re.IGNORECASE,
)
_API_KEY_WORD_PATTERN = re.compile(
    r"(?P<prefix>\bAPI\s+key\s*(?:=|:)\s*)(?P<secret>[^\s,;]+)",
    re.IGNORECASE,
)
_TOKEN_WORD_PATTERN = re.compile(
    r"(?P<prefix>\bToken\s+)(?P<secret>[^\s,;]+)",
    re.IGNORECASE,
)


def _replace_secret(match: re.Match[str]) -> str:
    return f"{match.group('prefix')}{REDACTED}"


def redact_secrets(text: str) -> str:
    """Return text with provider credentials replaced by the redaction marker.

    The redactor is deliberately deterministic and local-only: it targets common
    stderr spellings for API keys, tokens, passwords, and authorization bearer
    credentials while preserving non-secret context for diagnostics.
    """
    if not text:
        return text

    redacted = _BEARER_PATTERN.sub(_replace_secret, text)
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(_replace_secret, redacted)
    redacted = _API_KEY_WORD_PATTERN.sub(_replace_secret, redacted)
    redacted = _TOKEN_WORD_PATTERN.sub(_replace_secret, redacted)
    return redacted


_RATE_LIMIT_RE = re.compile(r"\b(?:429|rate\s*limit(?:ed)?|too\s+many\s+requests)\b", re.IGNORECASE)
_AUTH_RE = re.compile(r"\b(?:401|403|unauthori[sz]ed|forbidden|invalid\s+(?:api\s+)?key|authentication\s+failed|permission\s+denied)\b", re.IGNORECASE)
_TIMEOUT_RE = re.compile(r"\b(?:timeout|timed\s*out|deadline\s+exceeded)\b", re.IGNORECASE)
_UNAVAILABLE_RE = re.compile(r"\b(?:503|502|504|service\s+unavailable|bad\s+gateway|gateway\s+timeout|temporarily\s+unavailable|connection\s+refused|connection\s+reset)\b", re.IGNORECASE)


def classify_provider_failure(
    stderr: str,
    exit_code: int | None,
    timed_out: bool = False,
) -> ProviderDiagnostic:
    """Classify provider stderr/exit status into a stable diagnostic object."""
    redacted_stderr = redact_secrets(stderr)

    if timed_out or _TIMEOUT_RE.search(stderr):
        return ProviderDiagnostic(
            kind=ProviderFailureKind.TIMEOUT,
            message="provider request timed out",
            redacted_stderr=redacted_stderr,
            exit_code=exit_code,
            timed_out=timed_out,
        )
    if _RATE_LIMIT_RE.search(stderr):
        return ProviderDiagnostic(
            kind=ProviderFailureKind.RATE_LIMITED,
            message="provider rate limited request",
            redacted_stderr=redacted_stderr,
            exit_code=exit_code,
            timed_out=timed_out,
        )
    if _AUTH_RE.search(stderr):
        return ProviderDiagnostic(
            kind=ProviderFailureKind.AUTH_ERROR,
            message="provider authentication failed",
            redacted_stderr=redacted_stderr,
            exit_code=exit_code,
            timed_out=timed_out,
        )
    if _UNAVAILABLE_RE.search(stderr):
        return ProviderDiagnostic(
            kind=ProviderFailureKind.PROVIDER_UNAVAILABLE,
            message="provider unavailable",
            redacted_stderr=redacted_stderr,
            exit_code=exit_code,
            timed_out=timed_out,
        )

    exit_message = "provider failed"
    if exit_code is not None:
        exit_message = f"provider failed with exit code {exit_code}"
    return ProviderDiagnostic(
        kind=ProviderFailureKind.UNKNOWN,
        message=exit_message,
        redacted_stderr=redacted_stderr,
        exit_code=exit_code,
        timed_out=timed_out,
    )
