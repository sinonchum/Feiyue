from __future__ import annotations

from pydantic import Field

from feiyue_core.providers import ModelProfile, ProviderRole
from feiyue_core.schemas.common import FeiyueModel

from .teacher_policy import InterventionDecision, InterventionTrigger, TeacherInterventionContext, TeacherInterventionPolicy


class RoutingError(ValueError):
    pass


class RoutingDecision(FeiyueModel):
    selected_role: ProviderRole
    selected_profile: ModelProfile
    intervention_decision: InterventionDecision
    should_call_teacher: bool
    trigger: InterventionTrigger
    reason: str
    blocked_by_budget: bool = False
    teacher_unavailable: bool = False
    routing_metadata: dict[str, str] = Field(default_factory=dict)


class ModelRoleRouter:
    def __init__(
        self,
        *,
        student: ModelProfile,
        teacher: ModelProfile | None = None,
        teacher_policy: TeacherInterventionPolicy | None = None,
    ) -> None:
        if student.role != ProviderRole.STUDENT:
            raise RoutingError("student profile must have role student")
        if teacher is not None and teacher.role != ProviderRole.TEACHER:
            raise RoutingError("teacher profile must have role teacher")
        self.student = student
        self.teacher = teacher
        self.teacher_policy = teacher_policy or TeacherInterventionPolicy()

    def route(self, context: TeacherInterventionContext) -> RoutingDecision:
        intervention = self.teacher_policy.evaluate(context)
        if intervention.should_call_teacher:
            if self.teacher is None:
                return self._decision(
                    selected_profile=self.student,
                    intervention=intervention,
                    should_call_teacher=False,
                    reason="teacher required but no teacher profile configured",
                    teacher_unavailable=True,
                )
            return self._decision(
                selected_profile=self.teacher,
                intervention=intervention,
                should_call_teacher=True,
                reason=intervention.reason,
            )
        return self._decision(
            selected_profile=self.student,
            intervention=intervention,
            should_call_teacher=False,
            reason=intervention.reason,
        )

    @staticmethod
    def _decision(
        *,
        selected_profile: ModelProfile,
        intervention: InterventionDecision,
        should_call_teacher: bool,
        reason: str,
        teacher_unavailable: bool = False,
    ) -> RoutingDecision:
        return RoutingDecision(
            selected_role=selected_profile.role,
            selected_profile=selected_profile,
            intervention_decision=intervention,
            should_call_teacher=should_call_teacher,
            trigger=intervention.trigger,
            reason=reason,
            blocked_by_budget=intervention.blocked_by_budget,
            teacher_unavailable=teacher_unavailable,
            routing_metadata={
                "selected_provider": selected_profile.provider,
                "selected_model": selected_profile.model,
                "selected_role": selected_profile.role.value,
                "trigger": intervention.trigger.value,
            },
        )
