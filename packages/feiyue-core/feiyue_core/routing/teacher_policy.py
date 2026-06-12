from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from feiyue_core.providers import ProviderRole
from feiyue_core.schemas.common import FeiyueModel


class InterventionTrigger(StrEnum):
    NONE = "none"
    CONSECUTIVE_STUDENT_FAILURES = "consecutive_student_failures"
    UNKNOWN_FAILURE = "unknown_failure"
    HIGH_RISK_CANDIDATE = "high_risk_candidate"
    LOW_VERIFIER_CONFIDENCE = "low_verifier_confidence"
    TEACHER_BUDGET_EXHAUSTED = "teacher_budget_exhausted"


class TeacherInterventionContext(FeiyueModel):
    task_id: str
    student_failure_count: int = Field(ge=0)
    failure_category: str | None = None
    candidate_risk_level: Literal["low", "medium", "high"] = "low"
    verifier_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    teacher_calls_used: int = Field(default=0, ge=0)
    teacher_call_budget: int = Field(default=0, ge=0)


class InterventionDecision(FeiyueModel):
    should_call_teacher: bool
    next_role: ProviderRole
    trigger: InterventionTrigger
    reason: str
    blocked_by_budget: bool = False
    audit_metadata: dict[str, object] = Field(default_factory=dict)


class TeacherInterventionPolicy:
    def __init__(self, max_student_failures_before_teacher: int = 2, min_verifier_confidence: float = 0.6) -> None:
        self.max_student_failures_before_teacher = max_student_failures_before_teacher
        self.min_verifier_confidence = min_verifier_confidence

    def evaluate(self, context: TeacherInterventionContext) -> InterventionDecision:
        trigger, reason = self._select_trigger(context)
        if trigger == InterventionTrigger.NONE:
            return self._decision(
                context,
                should_call_teacher=False,
                next_role=ProviderRole.STUDENT,
                trigger=trigger,
                reason=reason,
            )
        if context.teacher_calls_used >= context.teacher_call_budget:
            return self._decision(
                context,
                should_call_teacher=False,
                next_role=ProviderRole.STUDENT,
                trigger=InterventionTrigger.TEACHER_BUDGET_EXHAUSTED,
                reason="teacher call budget exhausted",
                blocked_by_budget=True,
            )
        return self._decision(
            context,
            should_call_teacher=True,
            next_role=ProviderRole.TEACHER,
            trigger=trigger,
            reason=reason,
        )

    def _select_trigger(self, context: TeacherInterventionContext) -> tuple[InterventionTrigger, str]:
        if context.failure_category == "unknown_failure":
            return InterventionTrigger.UNKNOWN_FAILURE, "failure category is unknown_failure"
        if context.candidate_risk_level == "high":
            return InterventionTrigger.HIGH_RISK_CANDIDATE, "candidate risk level is high"
        if context.verifier_confidence is not None and context.verifier_confidence < self.min_verifier_confidence:
            return (
                InterventionTrigger.LOW_VERIFIER_CONFIDENCE,
                f"verifier confidence {context.verifier_confidence:g} below {self.min_verifier_confidence:g}",
            )
        if context.student_failure_count >= self.max_student_failures_before_teacher:
            return (
                InterventionTrigger.CONSECUTIVE_STUDENT_FAILURES,
                f"student failed {context.student_failure_count} times",
            )
        return InterventionTrigger.NONE, "continue with student model"

    @staticmethod
    def _decision(
        context: TeacherInterventionContext,
        *,
        should_call_teacher: bool,
        next_role: ProviderRole,
        trigger: InterventionTrigger,
        reason: str,
        blocked_by_budget: bool = False,
    ) -> InterventionDecision:
        return InterventionDecision(
            should_call_teacher=should_call_teacher,
            next_role=next_role,
            trigger=trigger,
            reason=reason,
            blocked_by_budget=blocked_by_budget,
            audit_metadata={
                "task_id": context.task_id,
                "student_failure_count": context.student_failure_count,
                "failure_category": context.failure_category,
                "candidate_risk_level": context.candidate_risk_level,
                "teacher_calls_used": context.teacher_calls_used,
                "teacher_call_budget": context.teacher_call_budget,
            },
        )
