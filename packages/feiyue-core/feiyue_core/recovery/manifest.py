from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field, field_serializer

from feiyue_core.schemas.common import FeiyueModel


class RecoveryManifest(FeiyueModel):
    session_id: str
    current_goal: str
    task_id: str | None = None
    active_project: str | None = None
    confirmed_facts: list[str] = Field(default_factory=list)
    known_mistakes: list[str] = Field(default_factory=list)
    do_not_repeat: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    pending_operations: list[str] = Field(default_factory=list)
    side_effect_checks: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    changed_files: list[str] = Field(default_factory=list)
    verified_outputs: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_safe_action: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("updated_at", when_used="json")
    def serialize_updated_at(self, value: datetime) -> str:
        normalized = value.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")
