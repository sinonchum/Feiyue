from __future__ import annotations

from feiyue_core.providers import ModelProfile, ProviderRole
from feiyue_core.routing.multi_worker_gate import (
    EscalationAuthorization,
    MultiWorkerRouter,
    RouteStatus,
    WorkerCapabilityProfile,
    WorkerRouteContext,
)


def _worker(profile_id: str, *capabilities: str) -> WorkerCapabilityProfile:
    return WorkerCapabilityProfile(
        profile_id=profile_id,
        model_profile=ModelProfile(
            provider="fake",
            model=profile_id,
            role=ProviderRole.STUDENT,
            cost_tier="low",
            strengths=list(capabilities),
        ),
        capabilities=list(capabilities),
        risk_ceiling="medium",
    )


def _teacher(profile_id: str = "teacher.fake") -> WorkerCapabilityProfile:
    return WorkerCapabilityProfile(
        profile_id=profile_id,
        model_profile=ModelProfile(
            provider="fake",
            model=profile_id,
            role=ProviderRole.TEACHER,
            cost_tier="high",
            strengths=["python", "debugging", "architecture"],
        ),
        capabilities=["python", "debugging", "architecture"],
        risk_ceiling="high",
    )


def test_low_risk_selects_weak_worker_without_provider_execution() -> None:
    router = MultiWorkerRouter(workers=[_worker("weak.python", "python"), _worker("weak.docs", "docs")], teacher=_teacher())

    plan = router.route(
        WorkerRouteContext(
            task_id="task.low-risk",
            required_capabilities=["python"],
            risk_level="low",
            evidence_ids=["fixture:low-risk"],
        )
    )

    assert plan.status == RouteStatus.SELECTED
    assert plan.worker_profile_ids == ["weak.python"]
    assert plan.teacher_profile_id is None
    assert plan.requires_teacher_authorization is False
    assert plan.provider_call_count == 0
    assert plan.reason_codes == ["worker_capability_match", "risk_within_worker_ceiling"]


def test_repeated_failure_recommends_teacher_but_blocks_without_authorization() -> None:
    router = MultiWorkerRouter(workers=[_worker("weak.python", "python")], teacher=_teacher("teacher.strong"))

    plan = router.route(
        WorkerRouteContext(
            task_id="task.repeated-failure",
            required_capabilities=["python"],
            risk_level="medium",
            evidence_ids=["trace:failure-1", "trace:failure-2"],
            student_failure_count=2,
            teacher_call_budget=1,
        )
    )

    assert plan.status == RouteStatus.BLOCKED
    assert plan.worker_profile_ids == ["weak.python"]
    assert plan.teacher_profile_id == "teacher.strong"
    assert plan.requires_teacher_authorization is True
    assert plan.provider_call_count == 0
    assert "teacher_escalation_authorization_missing" in plan.reason_codes
    assert "consecutive_student_failures" in plan.reason_codes


def test_authorized_teacher_escalation_records_reason_and_profile_without_execution() -> None:
    router = MultiWorkerRouter(workers=[_worker("weak.python", "python")], teacher=_teacher("teacher.strong"))
    authorization = EscalationAuthorization(
        authorization_id="auth.teacher.fake",
        authorized_by="test-suite",
        evidence_ids=["trace:failure-1", "trace:failure-2"],
        scopes=["teacher_escalation"],
    )

    plan = router.route(
        WorkerRouteContext(
            task_id="task.authorized-teacher",
            required_capabilities=["python"],
            risk_level="medium",
            evidence_ids=["trace:failure-1", "trace:failure-2"],
            student_failure_count=2,
            teacher_call_budget=1,
        ),
        authorization=authorization,
    )

    assert plan.status == RouteStatus.ESCALATED
    assert plan.worker_profile_ids == ["weak.python"]
    assert plan.teacher_profile_id == "teacher.strong"
    assert plan.authorization_id == "auth.teacher.fake"
    assert plan.provider_call_count == 0
    assert plan.reason_codes == [
        "worker_capability_match",
        "risk_within_worker_ceiling",
        "consecutive_student_failures",
        "teacher_escalation_authorized",
        "provider_execution_not_requested",
    ]


def test_high_risk_without_teacher_is_blocked_with_auditable_reason() -> None:
    router = MultiWorkerRouter(workers=[_worker("weak.python", "python")], teacher=None)

    plan = router.route(
        WorkerRouteContext(
            task_id="task.high-risk",
            required_capabilities=["python"],
            risk_level="high",
            evidence_ids=["fixture:high-risk"],
            teacher_call_budget=1,
        )
    )

    assert plan.status == RouteStatus.BLOCKED
    assert plan.teacher_profile_id is None
    assert "teacher_profile_unavailable" in plan.reason_codes
    assert "high_risk_candidate" in plan.reason_codes
