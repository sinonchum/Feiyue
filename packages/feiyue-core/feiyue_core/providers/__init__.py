"""Role-aware provider contracts for Feiyue."""

from .base import ModelProfile, ProviderRequest, ProviderResponse, ProviderRole
from .errors import ProviderError, ProviderErrorKind
from .fake import BaseProvider, FakeStudentProvider, FakeTeacherProvider

__all__ = [
    "BaseProvider",
    "FakeStudentProvider",
    "FakeTeacherProvider",
    "ModelProfile",
    "ProviderError",
    "ProviderErrorKind",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRole",
]
