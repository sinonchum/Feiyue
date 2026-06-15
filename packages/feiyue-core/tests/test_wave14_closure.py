from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.wave14_closure import Wave14ClosureRunner


def test_wave14_closure_runner_covers_all_four_closure_waves(tmp_path: Path) -> None:
    report = Wave14ClosureRunner(tmp_path).run(run_id="wave14-demo", write_report=True)

    assert report.run_id == "wave14-demo"
    assert report.status == "completed"
    assert report.waves_completed == ["Wave14-1", "Wave14-2", "Wave14-3", "Wave14-4"]
    assert report.longitudinal_task_count == 3
    assert report.longitudinal_teacher_call_rate_delta < 0
    assert report.operator_cockpit_v1_ready is True
    assert report.evidence_explorer_verified is True
    assert report.routing_learning_apply_loop_ready is True
    assert report.routing_table_mutated is False
    assert report.deploy_target_selected == "local-release-artifact"
    assert report.deploy_performed is False
    assert report.production_mutated is False
    assert report.requires_exact_deploy_approval is True

    evidence_path = tmp_path / ".hermes" / "wave14-closure" / "wave14-demo" / "evidence.json"
    report_path = tmp_path / ".hermes" / "wave14-closure" / "wave14-demo" / "report.md"
    assert evidence_path.exists()
    assert report_path.exists()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["wave14_1"]["task_program_executed"] is True
    assert payload["wave14_2"]["operator_cockpit_v1_ready"] is True
    assert payload["wave14_3"]["routing_learning_apply_loop_ready"] is True
    assert payload["wave14_4"]["deploy_readiness_ready"] is True


def test_wave14_closure_cli_writes_report(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.wave14_closure",
            "--root",
            str(tmp_path),
            "--run-id",
            "wave14-cli",
            "--write-report",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_id"] == "wave14-cli"
    assert payload["status"] == "completed"
    assert payload["deploy_performed"] is False
    assert (tmp_path / ".hermes" / "wave14-closure" / "wave14-cli" / "report.md").exists()
