from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.capability_history import CapabilityHistoryCollector


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_capability_history_ingests_live_profile_matrix_and_teacher_escalation(tmp_path: Path) -> None:
    matrix_root = tmp_path / ".hermes" / "live-matrices" / "matrix-demo"
    _write_json(
        matrix_root / "profiles" / "feiyue-weak-demo" / "round-01-safety" / "summary.json",
        {
            "run_id": "matrix-demo",
            "profile_id": "feiyue-weak-demo",
            "tier": "weak",
            "round": 1,
            "case_id": "safety",
            "profile_call_count": 1,
            "worker_result": {"duration_ms": 1234, "exit_code": 0, "timed_out": False},
            "verifier": {"passed": True, "quality_score": 1.0},
            "teacher_escalation_attempted": False,
        },
    )
    _write_json(
        tmp_path / ".hermes" / "live-teacher-escalations" / "teacher-demo" / "summary.json",
        {
            "run_id": "teacher-demo",
            "status": "completed",
            "worker_profile": "feiyue-weak-demo",
            "teacher_profile": "feiyue-strong-demo",
            "provider_call_count": 3,
            "teacher_escalation_attempted": True,
            "final_verifier_passed": True,
            "durations_ms": {"initial_worker": 10, "teacher": 20, "retry_worker": 30},
            "dry_run_only": True,
            "promotion_attempted": False,
            "production_mutated": False,
            "global_hermes_config_mutated": False,
        },
    )
    _write_json(
        tmp_path / ".hermes" / "live-teacher-escalations" / "teacher-variants" / "summary.json",
        {
            "run_id": "teacher-variants",
            "status": "completed",
            "worker_profile": "feiyue-weak-demo",
            "teacher_profile": "feiyue-strong-demo",
            "provider_call_count": 6,
            "teacher_escalation_count": 2,
            "controlled_failure_variants": ["invalid-structured-output", "forbidden-claim"],
            "variants": [{"status": "completed"}, {"status": "completed"}],
            "dry_run_only": True,
            "promotion_attempted": False,
            "production_mutated": False,
            "global_hermes_config_mutated": False,
        },
    )
    _write_json(
        tmp_path / ".hermes" / "real-creative-e2e" / "creative-demo" / "summary.json",
        {
            "run_id": "creative-demo",
            "status": "completed",
            "strong_profile": "feiyue-strong-demo",
            "provider_call_count": 1,
            "verifier_passed": True,
            "duration_ms": 777,
            "dry_run_only": True,
            "promotion_attempted": False,
            "production_mutated": False,
            "global_hermes_config_mutated": False,
        },
    )

    report = CapabilityHistoryCollector(tmp_path).build_report()

    live_records = [record for record in report.records if record.source_kind in {"live_profile_matrix", "controlled_teacher_escalation", "real_creative_e2e"}]
    assert len(live_records) == 4
    matrix_record = next(record for record in live_records if record.source_kind == "live_profile_matrix")
    assert matrix_record.profile_id == "feiyue-weak-demo"
    assert matrix_record.task_id == "safety"
    assert matrix_record.capability == "phase_c_live_profile_matrix"
    assert matrix_record.verified is True
    assert matrix_record.teacher_used is False
    assert matrix_record.provider_call_count == 1
    assert matrix_record.latency_ms == 1234

    teacher_record = next(record for record in live_records if record.source_kind == "controlled_teacher_escalation")
    assert teacher_record.profile_id == "feiyue-weak-demo"
    assert teacher_record.capability == "teacher_escalation_recovery"
    assert teacher_record.verified is True
    assert teacher_record.teacher_used is True
    assert teacher_record.provider_call_count == 3
    assert teacher_record.latency_ms == 60

    summary = report.profile_summaries["feiyue-weak-demo"]
    assert summary.total_runs == 3
    assert summary.verified_runs == 3
    assert summary.teacher_used_runs == 2
    assert summary.provider_call_count == 10

    creative_record = next(record for record in live_records if record.source_kind == "real_creative_e2e")
    assert creative_record.profile_id == "feiyue-strong-demo"
    assert creative_record.capability == "real_creative_to_execution"
    assert creative_record.verified is True
    assert creative_record.provider_call_count == 1
    assert creative_record.latency_ms == 777


def test_runs_cli_inspects_live_profile_matrix_and_controlled_teacher_escalation(tmp_path: Path) -> None:
    _write_json(tmp_path / ".hermes" / "live-matrices" / "matrix-cli" / "matrix-summary.json", {"run_id": "matrix-cli", "status": "completed"})
    _write_json(tmp_path / ".hermes" / "live-teacher-escalations" / "teacher-cli" / "summary.json", {"run_id": "teacher-cli", "status": "completed"})

    matrix = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "live-profile-matrix", "matrix-cli"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert matrix.returncode == 0, matrix.stderr
    assert json.loads(matrix.stdout)["run_id"] == "matrix-cli"

    teacher = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "controlled-teacher-escalation", "teacher-cli"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert teacher.returncode == 0, teacher.stderr
    assert json.loads(teacher.stdout)["run_id"] == "teacher-cli"
