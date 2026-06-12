import pytest
from pydantic import ValidationError

from feiyue_core.providers import FakeProfileRunner, ProfileRunRequest, ProfileRunResult


def test_fake_profile_runner_returns_canned_response_deterministically() -> None:
    runner = FakeProfileRunner(
        {
            "lane-v-student": "candidate patch from lane v student",
            "lane-v-teacher": "teacher critique from lane v teacher",
        }
    )
    request = ProfileRunRequest(
        prompt="Fix failing tests",
        role="student",
        profile="lane-v-student",
        source_ids=["task-123", "trace-456"],
    )

    first = runner.run(request)
    second = runner.run(request)

    assert first == second
    assert first == ProfileRunResult(
        stdout="candidate patch from lane v student",
        stderr="",
        exit_code=0,
    )


def test_fake_profile_runner_reports_missing_profile_without_subprocess_execution() -> None:
    runner = FakeProfileRunner({"known-profile": "known response"})
    request = ProfileRunRequest(
        prompt="Run missing profile",
        role="teacher",
        profile="missing-profile",
        source_ids=["source-001"],
    )

    result = runner.run(request)

    assert result.stdout == ""
    assert result.exit_code == 127
    assert result.timed_out is False
    assert "missing-profile" in result.stderr
    assert "not configured" in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prompt", ""),
        ("role", ""),
        ("profile", ""),
        ("source_ids", []),
    ],
)
def test_profile_run_request_validates_required_fields(field: str, value: object) -> None:
    payload: dict[str, object] = {
        "prompt": "Generate response",
        "role": "student",
        "profile": "lane-v-student",
        "source_ids": ["source-001"],
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        ProfileRunRequest(**payload)


def test_profile_run_request_rejects_blank_source_ids() -> None:
    with pytest.raises(ValidationError):
        ProfileRunRequest(
            prompt="Generate response",
            role="student",
            profile="lane-v-student",
            source_ids=["source-001", ""],
        )


def test_profile_run_result_defaults_to_not_timed_out() -> None:
    result = ProfileRunResult(stdout="ok", stderr="", exit_code=0)

    assert result.timed_out is False
