from feiyue_core.providers import ProviderRole
from feiyue_core.routing import InterventionTrigger, TeacherInterventionContext, TeacherInterventionPolicy


def test_teacher_policy_keeps_student_as_default_executor() -> None:
    decision = TeacherInterventionPolicy().evaluate(
        TeacherInterventionContext(
            task_id="task_policy_001",
            student_failure_count=0,
            failure_category=None,
            candidate_risk_level="low",
            verifier_confidence=0.95,
            teacher_calls_used=0,
            teacher_call_budget=2,
        )
    )

    assert decision.should_call_teacher is False
    assert decision.next_role == ProviderRole.STUDENT
    assert decision.trigger == InterventionTrigger.NONE
    assert decision.reason == "continue with student model"


def test_teacher_policy_triggers_after_consecutive_student_failures() -> None:
    decision = TeacherInterventionPolicy(max_student_failures_before_teacher=2).evaluate(
        TeacherInterventionContext(
            task_id="task_policy_002",
            student_failure_count=2,
            failure_category="assertion_failed",
            candidate_risk_level="medium",
            verifier_confidence=0.8,
            teacher_calls_used=0,
            teacher_call_budget=2,
        )
    )

    assert decision.should_call_teacher is True
    assert decision.next_role == ProviderRole.TEACHER
    assert decision.trigger == InterventionTrigger.CONSECUTIVE_STUDENT_FAILURES
    assert decision.reason == "student failed 2 times"


def test_teacher_policy_triggers_on_unknown_failure_even_before_threshold() -> None:
    decision = TeacherInterventionPolicy(max_student_failures_before_teacher=3).evaluate(
        TeacherInterventionContext(
            task_id="task_policy_003",
            student_failure_count=1,
            failure_category="unknown_failure",
            candidate_risk_level="low",
            verifier_confidence=0.9,
            teacher_calls_used=0,
            teacher_call_budget=1,
        )
    )

    assert decision.should_call_teacher is True
    assert decision.trigger == InterventionTrigger.UNKNOWN_FAILURE
    assert decision.reason == "failure category is unknown_failure"


def test_teacher_policy_triggers_for_high_risk_candidate() -> None:
    decision = TeacherInterventionPolicy().evaluate(
        TeacherInterventionContext(
            task_id="task_policy_004",
            student_failure_count=0,
            failure_category=None,
            candidate_risk_level="high",
            verifier_confidence=0.95,
            teacher_calls_used=0,
            teacher_call_budget=1,
        )
    )

    assert decision.should_call_teacher is True
    assert decision.next_role == ProviderRole.TEACHER
    assert decision.trigger == InterventionTrigger.HIGH_RISK_CANDIDATE
    assert decision.reason == "candidate risk level is high"


def test_teacher_policy_triggers_on_low_verifier_confidence() -> None:
    decision = TeacherInterventionPolicy(min_verifier_confidence=0.7).evaluate(
        TeacherInterventionContext(
            task_id="task_policy_005",
            student_failure_count=0,
            failure_category="assertion_failed",
            candidate_risk_level="low",
            verifier_confidence=0.4,
            teacher_calls_used=0,
            teacher_call_budget=1,
        )
    )

    assert decision.should_call_teacher is True
    assert decision.trigger == InterventionTrigger.LOW_VERIFIER_CONFIDENCE
    assert decision.reason == "verifier confidence 0.4 below 0.7"


def test_teacher_policy_blocks_teacher_when_budget_exhausted() -> None:
    decision = TeacherInterventionPolicy(max_student_failures_before_teacher=2).evaluate(
        TeacherInterventionContext(
            task_id="task_policy_006",
            student_failure_count=3,
            failure_category="assertion_failed",
            candidate_risk_level="medium",
            verifier_confidence=0.9,
            teacher_calls_used=1,
            teacher_call_budget=1,
        )
    )

    assert decision.should_call_teacher is False
    assert decision.next_role == ProviderRole.STUDENT
    assert decision.trigger == InterventionTrigger.TEACHER_BUDGET_EXHAUSTED
    assert decision.blocked_by_budget is True
    assert decision.reason == "teacher call budget exhausted"


def test_teacher_policy_serializes_audit_metadata() -> None:
    decision = TeacherInterventionPolicy().evaluate(
        TeacherInterventionContext(
            task_id="task_policy_007",
            student_failure_count=2,
            failure_category="assertion_failed",
            candidate_risk_level="medium",
            verifier_confidence=0.9,
            teacher_calls_used=0,
            teacher_call_budget=2,
        )
    )

    dumped = decision.model_dump(mode="json")

    assert dumped["trigger"] == "consecutive_student_failures"
    assert dumped["next_role"] == "teacher"
    assert dumped["audit_metadata"] == {
        "task_id": "task_policy_007",
        "student_failure_count": 2,
        "failure_category": "assertion_failed",
        "candidate_risk_level": "medium",
        "teacher_calls_used": 0,
        "teacher_call_budget": 2,
    }
