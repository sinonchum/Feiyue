from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.capability_history import CapabilityHistoryCollector
from feiyue_core.workflow.longitudinal_mini_program import LongitudinalMiniProgramRunner


def test_longitudinal_mini_program_records_improvement_and_history_records(tmp_path: Path) -> None:
    report = LongitudinalMiniProgramRunner(tmp_path).run(run_id="mini-demo", write_report=True)

    assert report.run_id == "mini-demo"
    assert report.status == "completed"
    assert report.batch_count == 3
    assert report.before.teacher_call_rate == 1.0
    assert report.after.teacher_call_rate == 0.0
    assert report.teacher_call_rate_delta == -1.0
    assert report.before.repeat_error_count > report.after.repeat_error_count
    assert report.global_hermes_config_mutated is False
    assert report.production_mutated is False
    assert report.promotion_attempted is False

    evidence_path = tmp_path / ".hermes" / "longitudinal-mini-programs" / "mini-demo" / "evidence.json"
    assert evidence_path.exists()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["source_kind"] == "longitudinal_mini_program"
    assert payload["batches"][0]["phase"] == "baseline"
    assert payload["batches"][-1]["phase"] == "routing_adjusted"

    history = CapabilityHistoryCollector(tmp_path).build_report()
    records = [record for record in history.records if record.source_kind == "longitudinal_mini_program"]
    assert len(records) == 3
    assert records[0].teacher_used is True
    assert records[-1].teacher_used is False


def test_runs_cli_runs_longitudinal_mini_program(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "longitudinal-mini-program",
            "--run-id",
            "mini-cli",
            "--write-report",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_id"] == "mini-cli"
    assert payload["status"] == "completed"
    assert payload["teacher_call_rate_delta"] < 0
    assert (tmp_path / ".hermes" / "longitudinal-mini-programs" / "mini-cli" / "report.md").exists()
