from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import TimestampedModel


class TaskType(StrEnum):
    CODE = "code"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    TOOL_OPERATION = "tool_operation"
    EVALUATION = "evaluation"
    PROMPT_OPTIMIZATION = "prompt_optimization"


class TaskStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskSpec(TimestampedModel):
    id: str
    title: str
    type: TaskType
    status: TaskStatus = TaskStatus.CREATED
    goal: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
