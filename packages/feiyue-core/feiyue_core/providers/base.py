from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


REDACTED = "[REDACTED]"
SECRET_KEYS = ("api_key", "authorization", "token", "password", "secret")


class ProviderRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    REVIEWER = "reviewer"
    LABELER = "labeler"
    JUDGE_AUX = "judge_aux"
    FALLBACK = "fallback"


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            if any(secret_key in key.lower() for secret_key in SECRET_KEYS):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_value(nested)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


class RedactedModel(FeiyueModel):
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        return redact_value(super().model_dump(*args, **kwargs))

    def __repr__(self) -> str:
        fields = ", ".join(f"{key}={value!r}" for key, value in self.model_dump(mode="json").items())
        return f"{self.__class__.__name__}({fields})"


class ModelProfile(RedactedModel):
    provider: str
    model: str
    role: ProviderRole
    cost_tier: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    max_teacher_calls: int | None = None
    api_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderRequest(RedactedModel):
    task_id: str
    role: ProviderRole
    prompt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(FeiyueModel):
    provider: str
    model: str
    role: ProviderRole
    request_id: str
    content: dict[str, Any]
    finish_reason: str = "stop"
    usage: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
