from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

from feiyue_core.creative.e2e_smoke import CreativeE2ESmokeRunner, run_creative_e2e_smoke


def test_creative_e2e_smoke_writes_curator_ready_evidence_without_side_effects(tmp_path: Path) -> None:
    project_root = tmp_path / "project"

    evidence = run_creative_e2e_smoke(
        project_root=project_root,
        run_id="wave5-5-test",
        seed="Turn a fuzzy human idea into a verifier-backed task contract.",
        write_report=True,
    )

    evidence_path = project_root / ".hermes" / "creative-e2e" / "wave5-5-test" / "evidence.json"
    report_path = project_root / ".hermes" / "creative-e2e" / "wave5-5-test" / "report.md"
    assert evidence_path.exists()
    assert report_path.exists()

    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert persisted["seed"] == "Turn a fuzzy human idea into a verifier-backed task contract."
    assert persisted["run_id"] == "wave5-5-test"
    assert persisted["selected_variant_id"]
    assert persisted["task_contract_id"]
    assert persisted["workflow_status"] == "verified"
    assert persisted["verifier_passed"] is True
    assert persisted["dry_run_only"] is True
    assert persisted["promotion_attempted"] is False
    assert persisted["curator_proposal_ready"] is True
    assert persisted["global_hermes_config_mutated"] is False
    assert persisted["provider_call_count"] == 0
    assert persisted["creative_brief"]["human_seed"] == persisted["seed"]
    assert persisted["task_contract"]["task_id"] == persisted["task_contract_id"]
    assert persisted["workflow_report"]["execution_performed"] is False
    assert evidence.evidence_path == evidence_path
    assert evidence.report_path == report_path

    report = report_path.read_text(encoding="utf-8")
    assert "# Creative-to-Execution E2E Smoke: wave5-5-test" in report
    assert "- dry_run_only: true" in report
    assert "- curator_proposal_ready: true" in report


def test_creative_e2e_smoke_rejects_unsafe_run_id(tmp_path: Path) -> None:
    runner = CreativeE2ESmokeRunner(project_root=tmp_path)

    try:
        runner.run(run_id="../escape", seed="safe seed")
    except ValueError as exc:
        assert "run_id" in str(exc)
    else:
        raise AssertionError("unsafe run_id should be rejected")


def test_creative_e2e_smoke_cli_writes_report(tmp_path: Path) -> None:
    project_root = tmp_path / "cli-project"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.creative.e2e_smoke",
            "--root",
            str(project_root),
            "--run-id",
            "cli-wave5-5",
            "--seed",
            "Ship a tiny safe creative-to-execution proof.",
            "--write-report",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "CREATIVE_E2E_SMOKE_OK" in completed.stdout
    assert "run_id: cli-wave5-5" in completed.stdout
    assert "workflow_status: verified" in completed.stdout
    assert "curator_proposal_ready: True" in completed.stdout
    assert (project_root / ".hermes" / "creative-e2e" / "cli-wave5-5" / "evidence.json").exists()
    assert (project_root / ".hermes" / "creative-e2e" / "cli-wave5-5" / "report.md").exists()


def test_creative_e2e_smoke_console_script_is_registered() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    scripts = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["scripts"]

    assert scripts["creative-e2e-smoke"] == "feiyue_core.creative.e2e_smoke:main"
