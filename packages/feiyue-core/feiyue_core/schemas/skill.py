from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import TimestampedModel


class SkillCandidateStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class SkillCandidate(TimestampedModel):
    id: str
    source_task_id: str
    source_trace_id: str
    title: str
    applicability: str
    content: str
    status: SkillCandidateStatus = SkillCandidateStatus.PROPOSED
    reviewer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
