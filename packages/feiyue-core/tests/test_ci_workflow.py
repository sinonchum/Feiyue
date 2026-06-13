from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_github_actions_ci_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists()


def test_ci_workflow_runs_core_quality_gates() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "actions/checkout" in workflow
    assert "actions/setup-python" in workflow
    assert "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true" in workflow
    assert "python -m pip install -e '.[dev]'" in workflow
    assert "git config --global user.email" in workflow
    assert "git config --global user.name" in workflow
    assert "python -m compileall -q feiyue_core" in workflow
    assert "python -m pytest -q" in workflow
    assert "SECRET_SCAN_OK" in workflow


def test_ci_workflow_runs_static_export_all_smoke() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "python -m feiyue_core.workflow.runs_export_all" in workflow
    assert "STATIC_EXPORT_ALL_OK" in workflow
    assert "test -f \"$TMP/report.zip\"" in workflow
    assert "test -f \"$TMP/report.extracted/manifest.json\"" in workflow


def test_ci_workflow_runs_provider_free_example_smoke() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "Provider-free example smoke" in workflow
    assert "python -m feiyue_core.examples.provider_free_smoke" in workflow
    assert "PROVIDER_FREE_EXAMPLE_SMOKE_OK" in workflow


def test_ci_workflow_runs_provider_free_benchmark_smoke() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "Provider-free benchmark smoke" in workflow
    assert "python -m feiyue_core.evaluation.benchmark_runner" in workflow
    assert "BENCHMARK_SMOKE_OK" in workflow
