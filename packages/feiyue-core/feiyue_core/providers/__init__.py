"""Role-aware provider contracts for Feiyue."""

from .base import ModelProfile, ProviderRequest, ProviderResponse, ProviderRole
from .diagnostics import (
    ProviderDiagnostic,
    ProviderFailureKind,
    classify_provider_failure,
    redact_secrets,
)
from .errors import ProviderError, ProviderErrorKind
from .fake import BaseProvider, FakeStudentProvider, FakeTeacherProvider
from .integration import ProfileRunOutcome, ProfileRunner, run_profile_with_diagnostic
from .profile_runner import FakeProfileRunner, ProfileRunRequest, ProfileRunResult

__all__ = [
    "BaseProvider",
    "FakeProfileRunner",
    "FakeStudentProvider",
    "FakeTeacherProvider",
    "ModelProfile",
    "ProfileRunOutcome",
    "ProfileRunRequest",
    "ProfileRunResult",
    "ProfileRunner",
    "ProviderDiagnostic",
    "ProviderError",
    "ProviderErrorKind",
    "ProviderFailureKind",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRole",
    "classify_provider_failure",
    "redact_secrets",
    "run_profile_with_diagnostic",
]
