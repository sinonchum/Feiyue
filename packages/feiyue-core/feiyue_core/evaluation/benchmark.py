"""Provider-free benchmark task suite contracts."""

from __future__ import annotations

from typing import Any

from pydantic import field_validator, model_validator

from feiyue_core.schemas.common import FeiyueModel


class BenchmarkTask(FeiyueModel):
    """A deterministic task contract for benchmark evaluation."""

    task_id: str
    required_capability_level: str
    expected_verifier: str
    category: str
    source_ids: list[str]

    @field_validator(
        "task_id",
        "required_capability_level",
        "expected_verifier",
        "category",
        mode="before",
    )
    @classmethod
    def _strip_and_validate_required_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must be non-empty")
            return stripped
        return value

    @field_validator("source_ids")
    @classmethod
    def _validate_source_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("source_ids must be non-empty")

        normalized_ids: list[str] = []
        for source_id in value:
            if not isinstance(source_id, str):
                raise TypeError("source_ids entries must be strings")
            stripped = source_id.strip()
            if not stripped:
                raise ValueError("source_ids entries must be non-empty")
            normalized_ids.append(stripped)
        return normalized_ids


class BenchmarkSuite(FeiyueModel):
    """A provider-free ordered suite of benchmark tasks."""

    suite_id: str
    tasks: list[BenchmarkTask]

    @field_validator("suite_id", mode="before")
    @classmethod
    def _strip_and_validate_suite_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("suite_id must be non-empty")
            return stripped
        return value

    @field_validator("tasks")
    @classmethod
    def _validate_tasks_non_empty(cls, value: list[BenchmarkTask]) -> list[BenchmarkTask]:
        if not value:
            raise ValueError("tasks must be non-empty")
        return value

    @model_validator(mode="after")
    def _validate_unique_task_ids(self) -> "BenchmarkSuite":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for task in self.tasks:
            if task.task_id in seen:
                duplicates.add(task.task_id)
            seen.add(task.task_id)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"task_id values must be unique: {duplicate_list}")
        return self

    def render_markdown(self) -> str:
        """Render deterministic Markdown without reordering input tasks."""

        lines = [
            f"# Benchmark Suite: {self.suite_id}",
            "",
            f"- Total Tasks: {len(self.tasks)}",
            "",
            "## Tasks",
            "",
        ]
        for index, task in enumerate(self.tasks, start=1):
            lines.extend(
                [
                    f"{index}. `{task.task_id}`",
                    f"   - Category: {task.category}",
                    f"   - Required Capability Level: {task.required_capability_level}",
                    f"   - Expected Verifier: {task.expected_verifier}",
                    f"   - Source IDs: {_render_ids(task.source_ids)}",
                ]
            )
        return "\n".join(lines) + "\n"


def default_toy_benchmark_suite() -> BenchmarkSuite:
    """Build a deterministic toy benchmark suite for provider-free smoke tests."""

    return BenchmarkSuite(
        suite_id="toy-benchmark-suite",
        tasks=[
            BenchmarkTask(
                task_id="toy.echo_contract",
                required_capability_level="L1",
                expected_verifier="pytest:tests/test_task_contract.py",
                category="contract",
                source_ids=["m9:lane-t", "toy:echo-contract"],
            ),
            BenchmarkTask(
                task_id="toy.capability_routing",
                required_capability_level="L2",
                expected_verifier="pytest:tests/test_capability_rules.py",
                category="routing",
                source_ids=["m9:lane-t", "toy:capability-routing"],
            ),
            BenchmarkTask(
                task_id="toy.safe_patch",
                required_capability_level="L2",
                expected_verifier="pytest:tests/test_side_effect_inspector.py",
                category="safety",
                source_ids=["m9:lane-t", "toy:safe-patch"],
            ),
        ],
    )


def _render_ids(values: list[str]) -> str:
    return ", ".join(values)
