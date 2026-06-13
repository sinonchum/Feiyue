"""Provider-free multi-worker route and teacher escalation gate."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator

from feiyue_core.providers import ModelProfile, ProviderRole
from feiyue_core.routing.teacher_policy import TeacherInterventionContext, TeacherInterventionPolicy
from feiyue_core.schemas.common import FeiyueModel

RiskLevel = Literal["low", "medium", "high"]
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


class RouteStatus(StrEnum):
    SELECTED = "selected"
    ESCALATED = "escalated"
    BLOCKED = "blocked"


class EscalationAuthorization(FeiyueModel):
    """Minimal local authorization record for real teacher role escalation."""

    authorization_id: str
    authorized_by: str
    evidence_ids: list[str]
    scopes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("authorization_id", "authorized_by")
    @classmethod
    def _required_string(cls, value: str) -> str:
        return _non_empty(value, "authorization field")

    @field_validator("evidence_ids", "scopes")
    @classmethod
    def _required_string_list(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("evidence_ids and scopes must be non-empty")
        return [_non_empty(item, "authorization list item") for item in value]

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


class WorkerCapabilityProfile(FeiyueModel):
    profile_id: str
    model_profile: ModelProfile
    capabilities: list[str] = Field(default_factory=list)
    risk_ceiling: RiskLevel = "low"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str) -> str:
        return _non_empty(value, "profile_id")

    @field_validator("capabilities")
    @classmethod
    def _validate_capabilities(cls, value: list[str]) -> list[str]:
        return [_non_empty(item, "capability") for item in value]


class WorkerRouteContext(FeiyueModel):
    task_id: str
    required_capabilities: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    evidence_ids: list[str]
    student_failure_count: int = Field(default=0, ge=0)
    failure_category: str | None = None
    verifier_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    teacher_calls_used: int = Field(default=0, ge=0)
    teacher_call_budget: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_id")
    @classmethod
    def _validate_task_id(cls, value: str) -> str:
        return _non_empty(value, "task_id")

    @field_validator("required_capabilities", "evidence_ids")
    @classmethod
    def _validate_string_lists(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("required_capabilities and evidence_ids must be non-empty")
        return [_non_empty(item, "route context list item") for item in value]


class WorkerRoutePlan(FeiyueModel):
    task_id: str
    status: RouteStatus
    worker_profile_ids: list[str]
    teacher_profile_id: str | None = None
    requires_teacher_authorization: bool = False
    authorization_id: str | None = None
    reason_codes: list[str]
    provider_call_count: int = Field(default=0, ge=0)
    audit_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_id")
    @classmethod
    def _validate_task_id(cls, value: str) -> str:
        return _non_empty(value, "task_id")

    @field_validator("worker_profile_ids", "reason_codes")
    @classmethod
    def _validate_string_lists(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("worker_profile_ids and reason_codes must be non-empty")
        return [_non_empty(item, "route plan list item") for item in value]


class MultiWorkerRouter:
    """Select workers and gate teacher escalation without provider execution."""

    def __init__(
        self,
        *,
        workers: list[WorkerCapabilityProfile],
        teacher: WorkerCapabilityProfile | None = None,
        teacher_policy: TeacherInterventionPolicy | None = None,
    ) -> None:
        if not workers:
            raise ValueError("workers must be non-empty")
        for worker in workers:
            if worker.model_profile.role != ProviderRole.STUDENT:
                raise ValueError("worker profiles must have role student")
        if teacher is not None and teacher.model_profile.role != ProviderRole.TEACHER:
            raise ValueError("teacher profile must have role teacher")
        self.workers = list(workers)
        self.teacher = teacher
        self.teacher_policy = teacher_policy or TeacherInterventionPolicy()

    def route(
        self,
        context: WorkerRouteContext,
        *,
        authorization: EscalationAuthorization | None = None,
    ) -> WorkerRoutePlan:
        selected_workers = self._select_workers(context)
        reason_codes = ["worker_capability_match"] if selected_workers else ["worker_capability_gap"]
        if selected_workers and all(_risk_allows(worker.risk_ceiling, context.risk_level) for worker in selected_workers):
            reason_codes.append("risk_within_worker_ceiling")
        elif selected_workers:
            reason_codes.append("risk_exceeds_worker_ceiling")

        intervention = self.teacher_policy.evaluate(
            TeacherInterventionContext(
                task_id=context.task_id,
                student_failure_count=context.student_failure_count,
                failure_category=context.failure_category,
                candidate_risk_level=context.risk_level,
                verifier_confidence=context.verifier_confidence,
                teacher_calls_used=context.teacher_calls_used,
                teacher_call_budget=context.teacher_call_budget,
            )
        )
        if intervention.trigger.value != "none":
            reason_codes.append(intervention.trigger.value)
        if intervention.blocked_by_budget:
            reason_codes.append("teacher_budget_exhausted")

        worker_ids = [worker.profile_id for worker in selected_workers] or [self.workers[0].profile_id]
        teacher_needed = intervention.should_call_teacher or context.risk_level == "high" or not selected_workers
        teacher_id = self.teacher.profile_id if self.teacher is not None and teacher_needed else None

        if teacher_needed:
            if self.teacher is None:
                return self._plan(
                    context,
                    status=RouteStatus.BLOCKED,
                    worker_ids=worker_ids,
                    teacher_id=None,
                    requires_teacher_authorization=True,
                    authorization_id=None,
                    reason_codes=_dedupe([*reason_codes, "teacher_profile_unavailable"]),
                    intervention_reason=intervention.reason,
                )
            if authorization is None or not authorization.allows("teacher_escalation"):
                blocked_reasons = [*reason_codes, "teacher_escalation_authorization_missing"]
                if authorization is not None:
                    blocked_reasons.append("authorization_scope_teacher_escalation_missing")
                return self._plan(
                    context,
                    status=RouteStatus.BLOCKED,
                    worker_ids=worker_ids,
                    teacher_id=self.teacher.profile_id,
                    requires_teacher_authorization=True,
                    authorization_id=getattr(authorization, "authorization_id", None),
                    reason_codes=_dedupe(blocked_reasons),
                    intervention_reason=intervention.reason,
                )
            return self._plan(
                context,
                status=RouteStatus.ESCALATED,
                worker_ids=worker_ids,
                teacher_id=self.teacher.profile_id,
                requires_teacher_authorization=True,
                authorization_id=authorization.authorization_id,
                reason_codes=_dedupe([*reason_codes, "teacher_escalation_authorized", "provider_execution_not_requested"]),
                intervention_reason=intervention.reason,
            )

        return self._plan(
            context,
            status=RouteStatus.SELECTED,
            worker_ids=worker_ids,
            teacher_id=None,
            requires_teacher_authorization=False,
            authorization_id=None,
            reason_codes=_dedupe(reason_codes),
            intervention_reason=intervention.reason,
        )

    def _select_workers(self, context: WorkerRouteContext) -> list[WorkerCapabilityProfile]:
        required = set(context.required_capabilities)
        candidates = [
            worker
            for worker in self.workers
            if required.issubset(set(worker.capabilities)) and _risk_allows(worker.risk_ceiling, context.risk_level)
        ]
        if candidates:
            return sorted(candidates, key=lambda worker: (len(worker.capabilities), worker.profile_id))[:1]
        capability_matches = [worker for worker in self.workers if required.issubset(set(worker.capabilities))]
        return sorted(capability_matches, key=lambda worker: (len(worker.capabilities), worker.profile_id))[:1]

    @staticmethod
    def _plan(
        context: WorkerRouteContext,
        *,
        status: RouteStatus,
        worker_ids: list[str],
        teacher_id: str | None,
        requires_teacher_authorization: bool,
        authorization_id: str | None,
        reason_codes: list[str],
        intervention_reason: str,
    ) -> WorkerRoutePlan:
        return WorkerRoutePlan(
            task_id=context.task_id,
            status=status,
            worker_profile_ids=worker_ids,
            teacher_profile_id=teacher_id,
            requires_teacher_authorization=requires_teacher_authorization,
            authorization_id=authorization_id,
            reason_codes=reason_codes,
            provider_call_count=0,
            audit_metadata={
                "task_id": context.task_id,
                "risk_level": context.risk_level,
                "required_capabilities": list(context.required_capabilities),
                "evidence_ids": list(context.evidence_ids),
                "intervention_reason": intervention_reason,
            },
        )


def _risk_allows(ceiling: RiskLevel, risk: RiskLevel) -> bool:
    return _RISK_ORDER[ceiling] >= _RISK_ORDER[risk]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized
