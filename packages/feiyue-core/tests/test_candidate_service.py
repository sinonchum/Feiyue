from feiyue_core.generation import CandidateService, CandidateServiceError
from feiyue_core.generation.candidate_service import CompletionProvider
from feiyue_core.providers import FakeStudentProvider, FakeTeacherProvider, ModelProfile, ProviderRole
from feiyue_core.routing import ModelRoleRouter, TeacherInterventionContext
from feiyue_core.schemas import CandidateStatus, StrategyVersion, TaskSpec, TaskStatus, TaskType


def task_spec() -> TaskSpec:
    return TaskSpec(
        id="task_service_001",
        title="Fix arithmetic helper",
        type=TaskType.CODE,
        status=TaskStatus.READY,
        goal="Make add return a + b",
        acceptance_criteria=["pytest passes", "git diff is clean"],
        metadata={"target_files": ["math_tools.py"], "constraints": ["Do not change tests"]},
    )


def strategy() -> StrategyVersion:
    return StrategyVersion(id="strategy_service_v1", name="student patch", config_hash="hash_service_v1")


def student_profile() -> ModelProfile:
    return ModelProfile(provider="fake", model="fake-student-001", role=ProviderRole.STUDENT, cost_tier="low")


def teacher_profile() -> ModelProfile:
    return ModelProfile(
        provider="fake",
        model="fake-teacher-001",
        role=ProviderRole.TEACHER,
        cost_tier="high",
        max_teacher_calls=2,
    )


def candidate_service(*, with_teacher: bool = True) -> CandidateService:
    student = student_profile()
    teacher = teacher_profile() if with_teacher else None
    providers: dict[ProviderRole, CompletionProvider] = {ProviderRole.STUDENT: FakeStudentProvider(student)}
    if teacher is not None:
        providers[ProviderRole.TEACHER] = FakeTeacherProvider(teacher)
    return CandidateService(router=ModelRoleRouter(student=student, teacher=teacher), providers=providers)


def test_candidate_service_routes_to_student_and_returns_candidate_with_audit_metadata() -> None:
    result = candidate_service().generate_candidate(
        task=task_spec(),
        strategy=strategy(),
        intervention_context=TeacherInterventionContext(task_id="task_service_001", student_failure_count=0),
        provider_metadata={"file_writes": {"math_tools.py": "def add(a, b):\n    return a + b\n"}},
    )

    assert result.candidate is not None
    assert result.teacher_guidance is None
    assert result.routing_decision.selected_role == ProviderRole.STUDENT
    assert result.prompt_artifact.name == "student_candidate_generation"
    assert result.prompt_artifact.rendered_hash.startswith("sha256:")

    candidate = result.candidate
    assert candidate.status == CandidateStatus.GENERATED
    assert candidate.task_id == "task_service_001"
    assert candidate.strategy_version_id == "strategy_service_v1"
    assert candidate.metadata["provider"] == "fake"
    assert candidate.metadata["model"] == "fake-student-001"
    assert candidate.metadata["model_role"] == "student"
    assert candidate.metadata["request_id"].startswith("fake-student-")
    assert candidate.metadata["prompt_template"] == "student_candidate_generation"
    assert candidate.metadata["prompt_template_version"] == "v0.1"
    assert candidate.metadata["prompt_template_hash"].startswith("sha256:")
    assert candidate.metadata["prompt_rendered_hash"].startswith("sha256:")
    assert candidate.metadata["routing_trigger"] == "none"
    assert candidate.metadata["routing_reason"] == "continue with student model"


def test_candidate_service_keeps_teacher_guidance_separate_from_candidate_parsing() -> None:
    result = candidate_service().generate_candidate(
        task=task_spec(),
        strategy=strategy(),
        intervention_context=TeacherInterventionContext(
            task_id="task_service_001",
            student_failure_count=3,
            teacher_calls_used=0,
            teacher_call_budget=1,
            failure_category="pytest_failure",
        ),
        provider_metadata={"failure_category": "pytest_failure", "evidence_excerpt": "assert 1 == 2"},
    )

    assert result.candidate is None
    assert result.teacher_guidance is not None
    assert result.teacher_guidance["kind"] == "teacher_guidance"
    assert result.routing_decision.selected_role == ProviderRole.TEACHER
    assert result.provider_response.role == ProviderRole.TEACHER


def test_candidate_service_fails_closed_when_selected_provider_is_missing() -> None:
    service = CandidateService(router=ModelRoleRouter(student=student_profile()), providers={})

    try:
        service.generate_candidate(
            task=task_spec(),
            strategy=strategy(),
            intervention_context=TeacherInterventionContext(task_id="task_service_001", student_failure_count=0),
        )
    except CandidateServiceError as exc:
        assert "student" in str(exc)
        assert "provider" in str(exc)
    else:
        raise AssertionError("CandidateServiceError was not raised")
