import pytest
from pydantic import ValidationError

from feiyue_core.providers import (
    FakeStudentProvider,
    FakeTeacherProvider,
    ModelProfile,
    ProviderError,
    ProviderErrorKind,
    ProviderRequest,
    ProviderRole,
)


def test_model_profile_records_role_and_redacts_secret() -> None:
    profile = ModelProfile(
        provider="nous",
        model="deepseek-v4-pro",
        role=ProviderRole.STUDENT,
        cost_tier="low",
        strengths=["code repair"],
        weaknesses=["long horizon planning"],
        api_key="fixture-api-key-value",
    )

    dumped = profile.model_dump(mode="json")
    rendered = repr(profile)

    assert dumped["role"] == "student"
    assert dumped["api_key"] == "[REDACTED]"
    assert "sk-test-secret" not in rendered
    assert "[REDACTED]" in rendered


def test_provider_request_redacts_authorization_metadata() -> None:
    request = ProviderRequest(
        task_id="task_provider_001",
        role=ProviderRole.STUDENT,
        prompt="Generate a candidate patch",
        metadata={"Authorization": "Bearer credential-fixture", "trace_id": "trace_001"},
    )

    dumped = request.model_dump(mode="json")
    rendered = repr(request)

    assert dumped["metadata"]["Authorization"] == "[REDACTED]"
    assert dumped["metadata"]["trace_id"] == "trace_001"
    assert "credential-fixture" not in rendered


def test_fake_student_provider_returns_deterministic_candidate_payload() -> None:
    provider = FakeStudentProvider(
        profile=ModelProfile(provider="fake", model="fake-student", role=ProviderRole.STUDENT, cost_tier="low")
    )
    request = ProviderRequest(
        task_id="task_provider_002",
        role=ProviderRole.STUDENT,
        prompt="Fix add",
        metadata={"file_writes": {"math_tools.py": "def add(a, b):\n    return a + b\n"}},
    )

    first = provider.complete(request)
    second = provider.complete(request)

    assert first == second
    assert first.provider == "fake"
    assert first.model == "fake-student"
    assert first.role == ProviderRole.STUDENT
    assert first.request_id.startswith("fake-student-")
    assert first.content["kind"] == "candidate"
    assert first.content["file_writes"] == {"math_tools.py": "def add(a, b):\n    return a + b\n"}
    assert first.finish_reason == "stop"


def test_fake_teacher_provider_returns_guidance_not_success_verdict() -> None:
    provider = FakeTeacherProvider(
        profile=ModelProfile(provider="fake", model="fake-teacher", role=ProviderRole.TEACHER, cost_tier="high")
    )
    request = ProviderRequest(
        task_id="task_provider_003",
        role=ProviderRole.TEACHER,
        prompt="Student failed pytest",
        metadata={"failure_category": "assertion_failed", "evidence_excerpt": "assert -1 == 3"},
    )

    response = provider.complete(request)

    assert response.role == ProviderRole.TEACHER
    assert response.content["kind"] == "teacher_guidance"
    assert response.content["failure_category"] == "assertion_failed"
    assert response.content["guidance"]
    assert "success" not in response.content
    assert response.content["must_be_verified_externally"] is True


def test_provider_role_mismatch_is_rejected() -> None:
    provider = FakeTeacherProvider(
        profile=ModelProfile(provider="fake", model="fake-teacher", role=ProviderRole.TEACHER, cost_tier="high")
    )
    request = ProviderRequest(task_id="task_provider_004", role=ProviderRole.STUDENT, prompt="Wrong role")

    with pytest.raises(ProviderError) as error_info:
        provider.complete(request)

    error = error_info.value
    assert error.kind == ProviderErrorKind.ROLE_MISMATCH
    assert error.retryable is False
    assert "teacher" in str(error)
    assert "student" in str(error)


def test_provider_error_classifies_retryable_and_non_retryable_failures() -> None:
    timeout = ProviderError.timeout(provider="fake", model="fake-student", request_id="req_timeout")
    rate_limit = ProviderError.rate_limited(
        provider="fake", model="fake-student", request_id="req_429", retry_after_seconds=2.5
    )
    auth = ProviderError.auth_error(provider="fake", model="fake-student", request_id="req_auth")
    invalid_json = ProviderError.invalid_json(
        provider="fake", model="fake-student", request_id="req_json", raw_text="{bad json}"
    )

    assert timeout.retryable is True
    assert rate_limit.retryable is True
    assert rate_limit.retry_after_seconds == 2.5
    assert auth.retryable is False
    assert invalid_json.retryable is False
    assert "{bad json}" not in invalid_json.model_dump(mode="json")["message"]


def test_model_profile_rejects_unknown_role() -> None:
    with pytest.raises(ValidationError):
        ModelProfile(provider="fake", model="bad", role="executor", cost_tier="low")
