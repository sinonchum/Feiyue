from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import TimestampedModel


class VerifierType(StrEnum):
    PYTEST = "pytest"
    LINT = "lint"
    BUILD = "build"
    HUMAN_CHECKLIST = "human_checklist"
    LLM_JUDGE = "llm_judge"
    CUSTOM = "custom"


class VerificationResult(TimestampedModel):
    id: str
    execution_run_id: str
    verifier_type: VerifierType
    verifier_name: str
    passed: bool
    score: float | None = None
    confidence: float | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    failure_category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
