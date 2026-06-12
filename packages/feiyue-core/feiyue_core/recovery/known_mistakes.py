from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import Field, field_serializer

from feiyue_core.schemas.common import FeiyueModel, RiskLevel


class MistakeScope(StrEnum):
    TURN = "turn"
    TASK = "task"
    PROJECT = "project"


class KnownMistake(FeiyueModel):
    mistake_id: str
    summary: str
    evidence_ref: str
    scope: MistakeScope
    severity: RiskLevel
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("created_at", when_used="json")
    def serialize_created_at(self, value: datetime) -> str:
        normalized = value.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")
