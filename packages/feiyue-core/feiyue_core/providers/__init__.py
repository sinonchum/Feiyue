"""Role-aware provider contracts for Feiyue."""

from .base import ModelProfile, ProviderRequest, ProviderResponse, ProviderRole
from .authorization import (
    AuthorizedProviderRunRecord,
    AuthorizedScope,
    ProviderRunEvidence,
    RealProviderAuthorization,
    build_provider_run_evidence,
    write_provider_run_evidence,
)
from .diagnostics import (
    ProviderDiagnostic,
    ProviderFailureKind,
    classify_provider_failure,
    redact_secrets,
)
from .errors import ProviderError, ProviderErrorKind
from .fake import BaseProvider, FakeStudentProvider, FakeTeacherProvider
from .integration import ProfileRunOutcome, ProfileRunner, run_profile_with_diagnostic
from .ollama_runner import CandidateWriteRepairingProfileRunner, OllamaCallEvidence, OllamaProfileRunner
from .profile_runner import (
    FakeProfileRunner,
    HermesProfileSubprocessRunner,
    ProfileRunRequest,
    ProfileRunResult,
)

__all__ = [
    "BaseProvider",
    "AuthorizedProviderRunRecord",
    "AuthorizedScope",
    "CandidateWriteRepairingProfileRunner",
    "FakeProfileRunner",
    "FakeStudentProvider",
    "FakeTeacherProvider",
    "HermesProfileSubprocessRunner",
    "ModelProfile",
    "OllamaCallEvidence",
    "OllamaProfileRunner",
    "ProfileRunOutcome",
    "ProfileRunRequest",
    "ProfileRunResult",
    "ProfileRunner",
    "ProviderDiagnostic",
    "ProviderError",
    "ProviderErrorKind",
    "ProviderFailureKind",
    "ProviderRunEvidence",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRole",
    "RealProviderAuthorization",
    "build_provider_run_evidence",
    "classify_provider_failure",
    "redact_secrets",
    "run_profile_with_diagnostic",
    "write_provider_run_evidence",
]
