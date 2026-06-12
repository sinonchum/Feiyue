from __future__ import annotations

from enum import StrEnum
from typing import Any

from .base import REDACTED


class ProviderErrorKind(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    INVALID_JSON = "invalid_json"
    ROLE_MISMATCH = "role_mismatch"
    UNKNOWN = "unknown"


class ProviderError(Exception):
    def __init__(
        self,
        *,
        kind: ProviderErrorKind,
        provider: str,
        model: str,
        message: str,
        retryable: bool,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.kind = kind
        self.provider = provider
        self.model = model
        self.message = message
        self.retryable = retryable
        self.request_id = request_id
        self.retry_after_seconds = retry_after_seconds
        self.details = details or {}
        super().__init__(self.__str__())

    def __str__(self) -> str:
        request = f" request_id={self.request_id}" if self.request_id else ""
        return f"{self.kind.value} from {self.provider}/{self.model}:{request} {self.message}"

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {
            "kind": self.kind.value if mode == "json" else self.kind,
            "provider": self.provider,
            "model": self.model,
            "message": self.message,
            "retryable": self.retryable,
            "request_id": self.request_id,
            "retry_after_seconds": self.retry_after_seconds,
            "details": self.details,
        }

    @classmethod
    def timeout(cls, *, provider: str, model: str, request_id: str | None = None) -> "ProviderError":
        return cls(
            kind=ProviderErrorKind.TIMEOUT,
            provider=provider,
            model=model,
            request_id=request_id,
            message="provider request timed out",
            retryable=True,
        )

    @classmethod
    def rate_limited(
        cls,
        *,
        provider: str,
        model: str,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> "ProviderError":
        return cls(
            kind=ProviderErrorKind.RATE_LIMIT,
            provider=provider,
            model=model,
            request_id=request_id,
            retry_after_seconds=retry_after_seconds,
            message="provider rate limited request",
            retryable=True,
        )

    @classmethod
    def auth_error(cls, *, provider: str, model: str, request_id: str | None = None) -> "ProviderError":
        return cls(
            kind=ProviderErrorKind.AUTH_ERROR,
            provider=provider,
            model=model,
            request_id=request_id,
            message="provider authentication failed",
            retryable=False,
        )

    @classmethod
    def invalid_json(
        cls,
        *,
        provider: str,
        model: str,
        request_id: str | None = None,
        raw_text: str = "",
    ) -> "ProviderError":
        return cls(
            kind=ProviderErrorKind.INVALID_JSON,
            provider=provider,
            model=model,
            request_id=request_id,
            message="provider returned invalid JSON",
            retryable=False,
            details={"raw_text": REDACTED if raw_text else ""},
        )

    @classmethod
    def role_mismatch(
        cls,
        *,
        provider: str,
        model: str,
        expected_role: str,
        actual_role: str,
        request_id: str | None = None,
    ) -> "ProviderError":
        return cls(
            kind=ProviderErrorKind.ROLE_MISMATCH,
            provider=provider,
            model=model,
            request_id=request_id,
            message=f"provider role {expected_role} cannot serve request role {actual_role}",
            retryable=False,
        )
