import pytest

from feiyue_core.generation import CandidateOutputError, CandidateOutputParser, ProviderCandidateOutput
from feiyue_core.providers import ModelProfile, ProviderResponse, ProviderRole
from feiyue_core.schemas import CandidateStatus, StrategyVersion, TaskSpec, TaskStatus, TaskType


def task_spec() -> TaskSpec:
    return TaskSpec(
        id="task_structured_001",
        title="Fix arithmetic helper",
        type=TaskType.CODE,
        status=TaskStatus.READY,
        goal="Make add return a + b",
        acceptance_criteria=["pytest passes"],
        metadata={"target_files": ["math_tools.py"]},
    )


def strategy() -> StrategyVersion:
    return StrategyVersion(id="strategy_student_v1", name="student patch", config_hash="hash_student_v1")


def student_profile() -> ModelProfile:
    return ModelProfile(provider="fake", model="fake-student", role=ProviderRole.STUDENT, cost_tier="low")


def provider_response(content: dict) -> ProviderResponse:
    return ProviderResponse(
        provider="fake",
        model="fake-student",
        role=ProviderRole.STUDENT,
        request_id="req_structured_001",
        content=content,
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
    )


def test_provider_candidate_output_validates_candidate_payload() -> None:
    output = ProviderCandidateOutput.model_validate(
        {
            "kind": "candidate",
            "summary": "Fix add helper",
            "file_writes": {"math_tools.py": "def add(a, b):\n    return a + b\n"},
            "assumptions": ["Only add is broken"],
            "risk_notes": ["Low risk pure function change"],
            "must_be_verified_externally": True,
        }
    )

    assert output.kind == "candidate"
    assert output.file_writes == {"math_tools.py": "def add(a, b):\n    return a + b\n"}
    assert output.must_be_verified_externally is True


def test_provider_candidate_output_rejects_missing_file_writes() -> None:
    with pytest.raises(CandidateOutputError) as error_info:
        CandidateOutputParser().parse_response(
            provider_response(
                {
                    "kind": "candidate",
                    "summary": "No files provided",
                    "must_be_verified_externally": True,
                }
            )
        )

    assert "file_writes" in str(error_info.value)
    assert error_info.value.provider == "fake"
    assert error_info.value.model == "fake-student"
    assert error_info.value.request_id == "req_structured_001"


def test_provider_candidate_output_rejects_teacher_guidance_as_candidate() -> None:
    with pytest.raises(CandidateOutputError) as error_info:
        CandidateOutputParser().parse_response(
            provider_response(
                {
                    "kind": "teacher_guidance",
                    "guidance": "Revise the candidate",
                    "must_be_verified_externally": True,
                }
            )
        )

    assert "kind" in str(error_info.value)
    assert "candidate" in str(error_info.value)


def test_candidate_output_parser_converts_provider_output_to_candidate() -> None:
    parsed = CandidateOutputParser().parse_response(
        provider_response(
            {
                "kind": "candidate",
                "summary": "Fix add helper",
                "file_writes": {"math_tools.py": "def add(a, b):\n    return a + b\n"},
                "assumptions": ["Only add is broken"],
                "risk_notes": ["Low risk pure function change"],
                "must_be_verified_externally": True,
            }
        )
    )

    candidate = parsed.to_candidate(task=task_spec(), strategy=strategy(), model_profile=student_profile())

    assert candidate.status == CandidateStatus.GENERATED
    assert candidate.task_id == "task_structured_001"
    assert candidate.strategy_version_id == "strategy_student_v1"
    assert candidate.summary == "Fix add helper"
    assert candidate.metadata["file_writes"] == {"math_tools.py": "def add(a, b):\n    return a + b\n"}
    assert candidate.metadata["provider"] == "fake"
    assert candidate.metadata["model"] == "fake-student"
    assert candidate.metadata["model_role"] == "student"
    assert candidate.metadata["request_id"] == "req_structured_001"
    assert candidate.metadata["assumptions"] == ["Only add is broken"]
    assert candidate.metadata["risk_notes"] == ["Low risk pure function change"]
    assert candidate.metadata["must_be_verified_externally"] is True


def test_candidate_output_parser_uses_stable_candidate_ids() -> None:
    response = provider_response(
        {
            "kind": "candidate",
            "summary": "Fix add helper",
            "file_writes": {"math_tools.py": "def add(a, b):\n    return a + b\n"},
            "must_be_verified_externally": True,
        }
    )
    parser = CandidateOutputParser()

    first = parser.parse_response(response).to_candidate(task=task_spec(), strategy=strategy(), model_profile=student_profile())
    second = parser.parse_response(response).to_candidate(task=task_spec(), strategy=strategy(), model_profile=student_profile())

    assert first.id == second.id
    assert first.id.startswith("cand_")
