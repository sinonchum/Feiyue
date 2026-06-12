from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import TimestampedModel


class StrategyVersion(TimestampedModel):
    id: str
    name: str
    config_hash: str
    prompt_refs: list[str] = Field(default_factory=list)
    tool_policy: dict[str, Any] = Field(default_factory=dict)
    parent_version_id: str | None = None
    metrics_snapshot: dict[str, Any] = Field(default_factory=dict)
