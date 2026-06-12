from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import TimestampedModel


class ExecutionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ExecutionRun(TimestampedModel):
    id: str
    candidate_id: str
    status: ExecutionStatus = ExecutionStatus.CREATED
    command: str
    exit_code: int | None = None
    duration_ms: int | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
