from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel, RiskLevel


class OperationStatus(StrEnum):
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILED = "reconciled"


OperationRiskLevel = RiskLevel


class OperationRecord(FeiyueModel):
    operation_id: str
    tool: str
    args_hash: str
    status: OperationStatus
    risk_level: OperationRiskLevel
    preconditions: dict[str, Any]
    postconditions: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[str] = Field(default_factory=list)
