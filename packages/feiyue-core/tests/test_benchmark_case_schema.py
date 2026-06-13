from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.evaluation import BenchmarkCase


def make_case(**overrides: object) -> BenchmarkCase:
    data = {
        "task_id": "real.file_edit.safe_patch",
        "category": "code_editing",
        "input": {"prompt": "Update the parser without network access."},
        "expected_artifacts": ["src/parser.py", "tests/test_parser.py"],
        "verifier_command": ["python", "-m", "pytest", "tests/test_parser.py", "-q"],
        "allowed_roles": ["weak", "strong"],
        "risk_level": "medium",
    }
    data.update(overrides)
    return BenchmarkCase(**data)


def test_benchmark_case_v1_round_trips_json() -> None:
    case = make_case()

    payload = case.model_dump_json()
    restored = BenchmarkCase.model_validate_json(payload)

    assert restored == case
    assert restored.schema_version == "feiyue.benchmark.case.v1"
    assert restored.verifier_command == ["python", "-m", "pytest", "tests/test_parser.py", "-q"]


def test_benchmark_case_accepts_safe_string_verifier_command() -> None:
    case = make_case(verifier_command="python -m pytest tests/test_parser.py -q")

    assert case.verifier_command == "python -m pytest tests/test_parser.py -q"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", " "),
        ("category", ""),
        ("expected_artifacts", []),
        ("expected_artifacts", ["dist/app.whl", " "]),
        ("verifier_command", []),
        ("verifier_command", ["python", ""]),
        ("verifier_command", "python -m pytest; curl example.com"),
        ("allowed_roles", []),
        ("allowed_roles", ["weak", " "]),
        ("risk_level", ""),
    ],
)
def test_benchmark_case_fails_fast_for_empty_or_unsafe_required_fields(field: str, value: object) -> None:
    with pytest.raises((ValidationError, ValueError)):
        make_case(**{field: value})


def test_benchmark_case_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        make_case(schema_version="feiyue.benchmark.case.v0")
