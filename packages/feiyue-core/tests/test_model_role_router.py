import pytest

from feiyue_core.providers import ModelProfile, ProviderRole
from feiyue_core.routing import (
    InterventionTrigger,
    ModelRoleRouter,
    RoutingError,
    TeacherInterventionContext,
    TeacherInterventionPolicy,
)


def student_profile() -> ModelProfile:
    return ModelProfile(provider="fake", model="fake-student", role=ProviderRole.STUDENT, cost_tier="low")


def teacher_profile() -> ModelProfile:
    return ModelProfile(provider="fake", model="fake-teacher", role=ProviderRole.TEACHER, cost_tier="high")


def test_model_role_router_selects_student_by_default() -> None:
    router = ModelRoleRouter(student=student_profile(), teacher=teacher_profile())

    decision = router.route(
        TeacherInterventionContext(
            task_id="task_router_001",
            student_failure_count=0,
            failure_category=None,
            candidate_risk_level="low",
            verifier_confidence=0.95,
            teacher_calls_used=0,
            teacher_call_budget=2,
        )
    )

    assert decision.selected_role == ProviderRole.STUDENT
    assert decision.selected_profile.model == "fake-student"
    assert decision.should_call_teacher is False
    assert decision.trigger == InterventionTrigger.NONE
    assert decision.reason == "continue with student model"


def test_model_role_router_selects_teacher_when_policy_triggers() -> None:
    router = ModelRoleRouter(
        student=student_profile(),
        teacher=teacher_profile(),
        teacher_policy=TeacherInterventionPolicy(max_student_failures_before_teacher=2),
    )

    decision = router.route(
        TeacherInterventionContext(
            task_id="task_router_002",
            student_failure_count=2,
            failure_category="assertion_failed",
            candidate_risk_level="medium",
            verifier_confidence=0.9,
            teacher_calls_used=0,
            teacher_call_budget=2,
        )
    )

    assert decision.selected_role == ProviderRole.TEACHER
    assert decision.selected_profile.model == "fake-teacher"
    assert decision.should_call_teacher is True
    assert decision.trigger == InterventionTrigger.CONSECUTIVE_STUDENT_FAILURES
    assert decision.reason == "student failed 2 times"


def test_model_role_router_keeps_student_when_teacher_budget_is_exhausted() -> None:
    router = ModelRoleRouter(
        student=student_profile(),
        teacher=teacher_profile(),
        teacher_policy=TeacherInterventionPolicy(max_student_failures_before_teacher=1),
    )

    decision = router.route(
        TeacherInterventionContext(
            task_id="task_router_003",
            student_failure_count=3,
            failure_category="assertion_failed",
            candidate_risk_level="medium",
            verifier_confidence=0.9,
            teacher_calls_used=1,
            teacher_call_budget=1,
        )
    )

    assert decision.selected_role == ProviderRole.STUDENT
    assert decision.selected_profile.model == "fake-student"
    assert decision.should_call_teacher is False
    assert decision.trigger == InterventionTrigger.TEACHER_BUDGET_EXHAUSTED
    assert decision.blocked_by_budget is True
    assert decision.reason == "teacher call budget exhausted"


def test_model_role_router_requires_student_profile() -> None:
    with pytest.raises(RoutingError) as error_info:
        ModelRoleRouter(student=teacher_profile(), teacher=teacher_profile())

    assert "student profile must have role student" in str(error_info.value)


def test_model_role_router_requires_teacher_role_for_teacher_profile() -> None:
    with pytest.raises(RoutingError) as error_info:
        ModelRoleRouter(student=student_profile(), teacher=student_profile())

    assert "teacher profile must have role teacher" in str(error_info.value)


def test_model_role_router_fails_closed_if_teacher_required_but_missing() -> None:
    router = ModelRoleRouter(
        student=student_profile(),
        teacher=None,
        teacher_policy=TeacherInterventionPolicy(max_student_failures_before_teacher=1),
    )

    decision = router.route(
        TeacherInterventionContext(
            task_id="task_router_004",
            student_failure_count=1,
            failure_category="assertion_failed",
            candidate_risk_level="medium",
            verifier_confidence=0.9,
            teacher_calls_used=0,
            teacher_call_budget=1,
        )
    )

    assert decision.selected_role == ProviderRole.STUDENT
    assert decision.selected_profile.model == "fake-student"
    assert decision.should_call_teacher is False
    assert decision.teacher_unavailable is True
    assert decision.trigger == InterventionTrigger.CONSECUTIVE_STUDENT_FAILURES
    assert decision.reason == "teacher required but no teacher profile configured"


def test_model_role_router_serializes_audit_metadata() -> None:
    router = ModelRoleRouter(student=student_profile(), teacher=teacher_profile())

    decision = router.route(
        TeacherInterventionContext(
            task_id="task_router_005",
            student_failure_count=2,
            failure_category="unknown_failure",
            candidate_risk_level="low",
            verifier_confidence=0.9,
            teacher_calls_used=0,
            teacher_call_budget=2,
        )
    )
    dumped = decision.model_dump(mode="json")

    assert dumped["selected_role"] == "teacher"
    assert dumped["selected_profile"]["role"] == "teacher"
    assert dumped["intervention_decision"]["trigger"] == "unknown_failure"
    assert dumped["routing_metadata"] == {
        "selected_provider": "fake",
        "selected_model": "fake-teacher",
        "selected_role": "teacher",
        "trigger": "unknown_failure",
    }
