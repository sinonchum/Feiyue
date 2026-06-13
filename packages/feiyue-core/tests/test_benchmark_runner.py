from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from feiyue_core.evaluation.benchmark_runner import (
    exact_match_score,
    run_toy_benchmark,
    token_f1_score,
)


def test_benchmark_metric_helpers_are_deterministic() -> None:
    assert exact_match_score("sum result", "sum result") == 1.0
    assert exact_match_score("sum result", "different") == 0.0
    assert token_f1_score("add two numbers", "add two numbers") == 1.0
    assert token_f1_score("add two", "add numbers") == 0.5
    assert token_f1_score("", "add numbers") == 0.0


def test_run_toy_benchmark_emits_stable_json_and_markdown(tmp_path: Path) -> None:
    json_path = tmp_path / "benchmark.json"
    markdown_path = tmp_path / "benchmark.md"

    report = run_toy_benchmark(output=json_path, output_markdown=markdown_path, quick=True)

    assert report.schema_version == "feiyue.benchmark.v1"
    assert report.suite_id == "toy-benchmark-suite"
    assert report.mode == "quick"
    assert report.cases_total == 3
    assert report.pass_rate == 2 / 3
    assert report.teacher_call_rate == 1 / 3
    assert report.average_cost == 2.5
    assert report.average_latency == 18.0
    assert report.cost_normalized_quality == report.pass_rate / report.average_cost
    assert [case.task_id for case in report.cases] == [
        "toy.echo_contract",
        "toy.capability_routing",
        "toy.safe_patch",
    ]
    assert report.cases[0].exact_match == 1.0
    assert report.cases[1].token_f1 == 0.5
    assert report.cases[2].passed is False
    assert json.loads(json_path.read_text(encoding="utf-8"))["pass_rate"] == 2 / 3
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Feiyue Benchmark Report" in markdown
    assert "- mode: quick" in markdown
    assert "- pass_rate: 0.6667" in markdown
    assert "| toy.safe_patch | safety | fail |" in markdown


def test_benchmark_runner_cli_quick_smoke(tmp_path: Path) -> None:
    json_path = tmp_path / "benchmark.json"
    markdown_path = tmp_path / "benchmark.md"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.evaluation.benchmark_runner",
            "--quick",
            "--output",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "BENCHMARK_SMOKE_OK" in completed.stdout
    assert "suite_id: toy-benchmark-suite" in completed.stdout
    assert "pass_rate: 0.6667" in completed.stdout
    assert json_path.exists()
    assert markdown_path.exists()
