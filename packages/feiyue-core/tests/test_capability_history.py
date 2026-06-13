import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.capability_history import CapabilityHistoryCollector


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_smoke(root, run_id, *, worker_profile="student-a", status="verified", teacher_profile=None, provider_call_count=1):
    _write_json(
        root / ".hermes" / "workflow-smokes" / run_id / "evidence.json",
        {
            "run_id": run_id,
            "task_id": f"task-{run_id}",
            "status": status,
            "worker_profile": worker_profile,
            "teacher_profile": teacher_profile,
            "provider_call_count": provider_call_count,
            "promotion_attempted": False,
            "workflow_report": {
                "task_id": f"task-{run_id}",
                "status": status,
                "verification_passed": status == "verified",
                "teacher_guidance_events": [{}] if teacher_profile else [],
                "started_at": "2026-01-01T00:00:00+00:00",
                "completed_at": "2026-01-01T00:01:00+00:00",
            },
            "written_at": "2026-01-01T00:02:00+00:00",
        },
    )


def _write_promotion(root, run_id, *, status="promoted"):
    _write_json(
        root / ".hermes" / "workflow-promotions" / run_id / "promotion-evidence.json",
        {
            "run_id": run_id,
            "task_id": f"task-{run_id}",
            "status": status,
            "promotion_attempted": True,
            "written_at": "2026-01-01T00:03:00+00:00",
        },
    )


def _write_multi_worker(root, run_id, *, worker_profile="student-b", status="needs_teacher"):
    _write_json(
        root / ".hermes" / "multi-worker-workflows" / run_id / "evidence.json",
        {
            "run_id": run_id,
            "task_id": "task-multi",
            "plan_id": "plan-1",
            "status": status,
            "worker_profile": worker_profile,
            "teacher_profile": "teacher-a",
            "provider_call_count": 2,
            "promotion_attempted": False,
            "workflow_report": {
                "task_id": "task-multi",
                "status": status,
                "verification_passed": False,
                "teacher_guidance_events": [{"reason": "fixture"}],
            },
            "dry_run_report": {"capability": "python_fix"},
            "written_at": "2026-01-01T00:04:00+00:00",
        },
    )


def test_capability_history_collects_longitudinal_records_from_workflow_evidence(tmp_path) -> None:
    _write_smoke(tmp_path, "run-1", worker_profile="student-a", status="verified")
    _write_promotion(tmp_path, "run-1", status="promoted")
    _write_multi_worker(tmp_path, "run-2")

    report = CapabilityHistoryCollector(tmp_path).build_report()

    assert report.routing_table_mutated is False
    assert report.total_records == 2
    records = {record.run_id: record for record in report.records}
    assert records["run-1"].profile_id == "student-a"
    assert records["run-1"].task_id == "task-run-1"
    assert records["run-1"].verified is True
    assert records["run-1"].teacher_used is False
    assert records["run-1"].promotion_attempted is True
    assert records["run-1"].promoted is True
    assert records["run-1"].source_evidence_path == ".hermes/workflow-smokes/run-1/evidence.json"
    assert records["run-2"].profile_id == "student-b"
    assert records["run-2"].capability == "python_fix"
    assert records["run-2"].teacher_used is True
    assert records["run-2"].provider_call_count == 2
    assert report.profile_summaries["student-a"].verified_runs == 1
    assert report.profile_summaries["student-b"].teacher_used_runs == 1


def test_capability_history_write_report_persists_jsonl_and_latest_without_mutating_routing(tmp_path) -> None:
    _write_smoke(tmp_path, "run-1", worker_profile="student-a", status="verified")
    routing_path = tmp_path / ".hermes" / "model-routing.yaml"
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    original_routing = "routes:\n  worker:\n    primary: student-a\n"
    routing_path.write_text(original_routing, encoding="utf-8")

    report = CapabilityHistoryCollector(tmp_path).write_report()

    output_dir = tmp_path / ".hermes" / "capability-history"
    assert (output_dir / "history.jsonl").exists()
    lines = (output_dir / "history.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["routing_table_mutated"] is False
    latest = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))
    assert latest["total_records"] == 1
    assert latest["routing_table_mutated"] is False
    assert "Capability History Report" in (output_dir / "latest.md").read_text(encoding="utf-8")
    assert routing_path.read_text(encoding="utf-8") == original_routing
    assert report.routing_table_mutated is False


def test_runs_cli_capability_history_writes_report(tmp_path) -> None:
    _write_smoke(tmp_path, "run-1", worker_profile="student-a", status="verified")

    env = {**os.environ, "PYTHONPATH": f"{Path(__file__).parents[1]}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "capability-history", "--write-report"],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )

    payload = json.loads(completed.stdout)
    assert payload["total_records"] == 1
    assert payload["records"][0]["profile_id"] == "student-a"
    assert payload["routing_table_mutated"] is False
    assert (tmp_path / ".hermes" / "capability-history" / "history.jsonl").exists()
