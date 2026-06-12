from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import TimestampedModel


class CandidateStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    APPLIED = "applied"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"


class Candidate(TimestampedModel):
    id: str
    task_id: str
    status: CandidateStatus = CandidateStatus.DRAFT
    strategy_version_id: str | None = None
    summary: str
    artifact_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
