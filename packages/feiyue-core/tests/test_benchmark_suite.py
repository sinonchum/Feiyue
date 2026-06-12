"""Tests for provider-free benchmark task suites."""

import pytest
from pydantic import ValidationError

from feiyue_core.evaluation import (
    BenchmarkSuite,
    BenchmarkTask,
    default_toy_benchmark_suite,
)


def test_benchmark_task_normalizes_and_validates_required_fields() -> None:
    task = BenchmarkTask(
        task_id="  toy.task  ",
        required_capability_level="  L1  ",
        expected_verifier="  pytest:tests/test_toy.py  ",
        category="  unit  ",
        source_ids=["  spec:m9  "],
    )

    assert task.task_id == "toy.task"
    assert task.required_capability_level == "L1"
    assert task.expected_verifier == "pytest:tests/test_toy.py"
    assert task.category == "unit"
    assert task.source_ids == ["spec:m9"]


@pytest.mark.parametrize(
    "field_name",
    ["task_id", "required_capability_level", "expected_verifier", "category"],
)
def test_benchmark_task_rejects_empty_required_strings(field_name: str) -> None:
    values = {
        "task_id": "toy.task",
        "required_capability_level": "L1",
        "expected_verifier": "pytest:tests/test_toy.py",
        "category": "unit",
        "source_ids": ["spec:m9"],
    }
    values[field_name] = "  "

    with pytest.raises(ValidationError):
        BenchmarkTask(**values)


@pytest.mark.parametrize("source_ids", [[], ["ok", "  "]])
def test_benchmark_task_rejects_invalid_source_ids(source_ids: list[str]) -> None:
    with pytest.raises(ValidationError):
        BenchmarkTask(
            task_id="toy.task",
            required_capability_level="L1",
            expected_verifier="pytest:tests/test_toy.py",
            category="unit",
            source_ids=source_ids,
        )


def test_benchmark_suite_preserves_input_order_and_rejects_duplicate_task_ids() -> None:
    first = BenchmarkTask(
        task_id="b.task",
        required_capability_level="L2",
        expected_verifier="pytest:b",
        category="integration",
        source_ids=["source:b"],
    )
    second = BenchmarkTask(
        task_id="a.task",
        required_capability_level="L1",
        expected_verifier="pytest:a",
        category="unit",
        source_ids=["source:a"],
    )

    suite = BenchmarkSuite(suite_id="  toy-suite  ", tasks=[first, second])

    assert suite.suite_id == "toy-suite"
    assert [task.task_id for task in suite.tasks] == ["b.task", "a.task"]

    with pytest.raises(ValidationError):
        BenchmarkSuite(suite_id="duplicate-suite", tasks=[first, first])


def test_benchmark_suite_rejects_empty_suite_and_empty_suite_id() -> None:
    task = BenchmarkTask(
        task_id="toy.task",
        required_capability_level="L1",
        expected_verifier="pytest:tests/test_toy.py",
        category="unit",
        source_ids=["spec:m9"],
    )

    with pytest.raises(ValidationError):
        BenchmarkSuite(suite_id="  ", tasks=[task])

    with pytest.raises(ValidationError):
        BenchmarkSuite(suite_id="toy-suite", tasks=[])


def test_benchmark_suite_renders_deterministic_markdown() -> None:
    suite = BenchmarkSuite(
        suite_id="toy-suite",
        tasks=[
            BenchmarkTask(
                task_id="task.one",
                required_capability_level="L1",
                expected_verifier="pytest:one",
                category="unit",
                source_ids=["spec:one", "fixture:one"],
            ),
            BenchmarkTask(
                task_id="task.two",
                required_capability_level="L2",
                expected_verifier="pytest:two",
                category="integration",
                source_ids=["spec:two"],
            ),
        ],
    )

    assert suite.render_markdown() == (
        "# Benchmark Suite: toy-suite\n"
        "\n"
        "- Total Tasks: 2\n"
        "\n"
        "## Tasks\n"
        "\n"
        "1. `task.one`\n"
        "   - Category: unit\n"
        "   - Required Capability Level: L1\n"
        "   - Expected Verifier: pytest:one\n"
        "   - Source IDs: spec:one, fixture:one\n"
        "2. `task.two`\n"
        "   - Category: integration\n"
        "   - Required Capability Level: L2\n"
        "   - Expected Verifier: pytest:two\n"
        "   - Source IDs: spec:two\n"
    )


def test_default_toy_benchmark_suite_is_provider_free_and_deterministic() -> None:
    first = default_toy_benchmark_suite()
    second = default_toy_benchmark_suite()

    assert first == second
    assert first.suite_id == "toy-benchmark-suite"
    assert len(first.tasks) >= 3
    assert [task.task_id for task in first.tasks] == [
        "toy.echo_contract",
        "toy.capability_routing",
        "toy.safe_patch",
    ]
    assert all(task.source_ids for task in first.tasks)
    assert "openai" not in first.render_markdown().lower()
    assert "anthropic" not in first.render_markdown().lower()
