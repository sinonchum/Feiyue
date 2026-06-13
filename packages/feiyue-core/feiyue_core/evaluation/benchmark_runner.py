from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

from pydantic import Field

from feiyue_core.evaluation.benchmark import default_toy_benchmark_suite
from feiyue_core.schemas.common import FeiyueModel


class BenchmarkCaseResult(FeiyueModel):
    task_id: str
    category: str
    expected: str
    actual: str
    exact_match: float
    token_f1: float
    passed: bool
    teacher_calls: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0


class BenchmarkReport(FeiyueModel):
    schema_version: str = "feiyue.benchmark.v1"
    suite_id: str
    mode: str
    cases_total: int
    passed: int
    failed: int
    pass_rate: float
    teacher_call_rate: float
    average_cost: float
    average_latency: float
    cost_normalized_quality: float
    cases: list[BenchmarkCaseResult] = Field(default_factory=list)

    def render_markdown(self) -> str:
        lines = [
            "# Feiyue Benchmark Report",
            "",
            f"- schema_version: {self.schema_version}",
            f"- suite_id: {self.suite_id}",
            f"- mode: {self.mode}",
            f"- cases_total: {self.cases_total}",
            f"- pass_rate: {_fmt(self.pass_rate)}",
            f"- teacher_call_rate: {_fmt(self.teacher_call_rate)}",
            f"- average_cost: {_fmt(self.average_cost)}",
            f"- average_latency: {_fmt(self.average_latency)}",
            f"- cost_normalized_quality: {_fmt(self.cost_normalized_quality)}",
            "",
            "## Cases",
            "",
            "| task_id | category | status | exact_match | token_f1 | teacher_calls | cost | latency_ms |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for case in self.cases:
            status = "pass" if case.passed else "fail"
            lines.append(
                "| "
                f"{case.task_id} | {case.category} | {status} | {_fmt(case.exact_match)} | "
                f"{_fmt(case.token_f1)} | {case.teacher_calls} | {_fmt(case.cost)} | {_fmt(case.latency_ms)} |"
            )
        return "\n".join(lines) + "\n"


def exact_match_score(actual: str, expected: str) -> float:
    return 1.0 if actual.strip() == expected.strip() else 0.0


def token_f1_score(actual: str, expected: str) -> float:
    actual_tokens = _tokens(actual)
    expected_tokens = _tokens(expected)
    if not actual_tokens or not expected_tokens:
        return 0.0
    common = 0
    remaining = expected_tokens.copy()
    for token in actual_tokens:
        if token in remaining:
            common += 1
            remaining.remove(token)
    if common == 0:
        return 0.0
    precision = common / len(actual_tokens)
    recall = common / len(expected_tokens)
    return round((2 * precision * recall) / (precision + recall), 4)


def run_toy_benchmark(
    *,
    output: str | Path | None = None,
    output_markdown: str | Path | None = None,
    quick: bool = False,
) -> BenchmarkReport:
    suite = default_toy_benchmark_suite()
    mode = "quick" if quick else "full"
    case_specs = [
        {
            "task_id": "toy.echo_contract",
            "expected": "render task contract exactly",
            "actual": "render task contract exactly",
            "teacher_calls": 0,
            "cost": 1.5,
            "latency_ms": 12.0,
            "passed": True,
        },
        {
            "task_id": "toy.capability_routing",
            "expected": "route safely",
            "actual": "route capability",
            "teacher_calls": 1,
            "cost": 2.5,
            "latency_ms": 18.0,
            "passed": True,
        },
        {
            "task_id": "toy.safe_patch",
            "expected": "block unsafe side effect",
            "actual": "allow unsafe side effect",
            "teacher_calls": 0,
            "cost": 3.5,
            "latency_ms": 24.0,
            "passed": False,
        },
    ]
    categories = {task.task_id: task.category for task in suite.tasks}
    cases = [
        BenchmarkCaseResult(
            task_id=spec["task_id"],
            category=categories[spec["task_id"]],
            expected=spec["expected"],
            actual=spec["actual"],
            exact_match=exact_match_score(spec["actual"], spec["expected"]),
            token_f1=token_f1_score(spec["actual"], spec["expected"]),
            passed=spec["passed"],
            teacher_calls=spec["teacher_calls"],
            cost=spec["cost"],
            latency_ms=spec["latency_ms"],
        )
        for spec in case_specs
    ]
    passed = sum(1 for case in cases if case.passed)
    cases_total = len(cases)
    average_cost = sum(case.cost for case in cases) / cases_total
    average_latency = sum(case.latency_ms for case in cases) / cases_total
    pass_rate = passed / cases_total
    report = BenchmarkReport(
        suite_id=suite.suite_id,
        mode=mode,
        cases_total=cases_total,
        passed=passed,
        failed=cases_total - passed,
        pass_rate=pass_rate,
        teacher_call_rate=sum(case.teacher_calls for case in cases) / cases_total,
        average_cost=average_cost,
        average_latency=average_latency,
        cost_normalized_quality=pass_rate / average_cost if average_cost else 0.0,
        cases=cases,
    )
    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if output_markdown is not None:
        markdown_path = Path(output_markdown)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(report.render_markdown(), encoding="utf-8")
    return report


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m feiyue_core.evaluation.benchmark_runner",
        description="Run deterministic provider-free Feiyue benchmark smoke.",
    )
    parser.add_argument("--quick", action="store_true", help="Run the tiny CI-safe benchmark fixture")
    parser.add_argument("--output", required=True, help="Path for benchmark JSON report")
    parser.add_argument("--output-markdown", required=True, help="Path for benchmark Markdown summary")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_toy_benchmark(output=args.output, output_markdown=args.output_markdown, quick=args.quick)
    print(f"suite_id: {report.suite_id}")
    print(f"mode: {report.mode}")
    print(f"cases_total: {report.cases_total}")
    print(f"pass_rate: {_fmt(report.pass_rate)}")
    print(f"json: {Path(args.output)}")
    print(f"markdown: {Path(args.output_markdown)}")
    print("BENCHMARK_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
