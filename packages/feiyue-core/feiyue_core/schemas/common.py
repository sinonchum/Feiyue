from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class FeiyueModel(BaseModel):
    """Base model for Feiyue contracts with stable JSON serialization."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)


class TimestampedModel(FeiyueModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        normalized = value.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")


class MetadataMixin(FeiyueModel):
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
