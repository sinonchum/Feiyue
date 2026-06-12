from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import Field, field_serializer

from .common import FeiyueModel


class TraceEventType(StrEnum):
    USER_MESSAGE_PERSISTED = "user_message_persisted"
    CONTEXT_BUILT = "context_built"
    MODEL_CALL_STARTED = "model_call_started"
    MODEL_ERROR = "model_error"
    MODEL_CALL_FINISHED = "model_call_finished"
    TOOL_OPERATION_STARTED = "tool_operation_started"
    TOOL_OPERATION_FINISHED = "tool_operation_finished"
    TOOL_OPERATION_UNKNOWN = "tool_operation_unknown"
    MANIFEST_UPDATED = "manifest_updated"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"


class TraceEvent(FeiyueModel):
    id: str
    session_id: str
    type: TraceEventType
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        normalized = value.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")
