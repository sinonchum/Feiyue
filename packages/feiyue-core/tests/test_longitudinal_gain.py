import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.longitudinal_gain import LongitudinalGainEvaluator


def _append_history(path: Path, **payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload) + "\n")


def _record(run_id: str, day: int, *, verified: bool, teacher_used: bool, cost_usd: float | None = None, latency_ms: float | None = None) -> dict:
    payload = {
        "profile_id": "student-a",
        "task_id": "task-python",
        "capability": "python_fix",
        "run_id": run_id,
        "source_kind": "workflow_smoke",
        "status": "verified" if verified else "failed",
        "verified": verified,
        "teacher_used": teacher_used,
        "provider_call_count": 0,
        "promotion_attempted": False,
        "promoted": False,
        "source_evidence_path": f"fixture/{run_id}.json",
        "observed_at": f"2026-01-{day:02d}T00:00:00+00:00",
        "routing_table_mutated": False,
    }
    if cost_usd is not None:
        payload["cost_usd"] = cost_usd
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    return payload


def test_longitudinal_gain_computes_before_after_deltas_from_history_jsonl(tmp_path) -> None:
    history_path = tmp_path / ".hermes" / "capability-history" / "history.jsonl"
    fixtures = [
        _record("run-1", 1, verified=False, teacher_used=True, cost_usd=0.30, latency_ms=3000),
        _record("run-2", 2, verified=True, teacher_used=True, cost_usd=0.20, latency_ms=2000),
        _record("run-3", 3, verified=True, teacher_used=False, cost_usd=0.10, latency_ms=1000),
        _record("run-4", 4, verified=True, teacher_used=False, cost_usd=0.10, latency_ms=800),
    ]
    for item in fixtures:
        _append_history(history_path, **item)

    report = LongitudinalGainEvaluator.from_history_path(history_path, min_samples=2, window_size=2).build_report()

    assert report.routing_table_mutated is False
    assert report.total_records == 4
    assert report.total_groups == 1
    group = report.groups[0]
    assert group.profile_id == "student-a"
    assert group.task_id == "task-python"
    assert group.capability == "python_fix"
    assert group.before.sample_count == 2
    assert group.after.sample_count == 2
    assert group.before.pass_rate == 0.5
    assert group.after.pass_rate == 1.0
    assert group.pass_rate_delta == 0.5
    assert group.before.teacher_call_rate == 1.0
    assert group.after.teacher_call_rate == 0.0
    assert group.teacher_call_rate_delta == -1.0
    assert group.before.average_cost_usd == 0.25
    assert group.after.average_cost_usd == 0.1
    assert group.cost_usd_delta == -0.15
    assert group.before.average_latency_ms == 2500
    assert group.after.average_latency_ms == 900
    assert group.latency_ms_delta == -1600
    assert group.confidence_label == "low"
    assert group.status == "evaluated"


def test_longitudinal_gain_fails_closed_when_windows_too_small(tmp_path) -> None:
    history_path = tmp_path / ".hermes" / "capability-history" / "history.jsonl"
    _append_history(history_path, **_record("run-1", 1, verified=True, teacher_used=False))
    _append_history(history_path, **_record("run-2", 2, verified=True, teacher_used=False))
    _append_history(history_path, **_record("run-3", 3, verified=True, teacher_used=False))

    report = LongitudinalGainEvaluator.from_history_path(history_path, min_samples=2, window_size=2).build_report()

    group = report.groups[0]
    assert group.status == "insufficient_data"
    assert group.confidence_label == "insufficient_data"
    assert group.pass_rate_delta is None
    assert group.teacher_call_rate_delta is None
    assert group.before.sample_count == 0
    assert group.after.sample_count == 0


def test_longitudinal_gain_write_report_persists_latest_without_mutating_routing(tmp_path) -> None:
    history_path = tmp_path / ".hermes" / "capability-history" / "history.jsonl"
    for item in [
        _record("run-1", 1, verified=False, teacher_used=True),
        _record("run-2", 2, verified=True, teacher_used=True),
        _record("run-3", 3, verified=True, teacher_used=False),
        _record("run-4", 4, verified=True, teacher_used=False),
    ]:
        _append_history(history_path, **item)
    routing_path = tmp_path / ".hermes" / "model-routing.yaml"
    original_routing = "routes:\n  worker:\n    primary: student-a\n"
    routing_path.write_text(original_routing, encoding="utf-8")

    report = LongitudinalGainEvaluator.from_history_path(history_path, min_samples=2, window_size=2).write_report(tmp_path)

    output_dir = tmp_path / ".hermes" / "longitudinal-gain"
    latest = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))
    assert latest["routing_table_mutated"] is False
    assert latest["groups"][0]["status"] == "evaluated"
    assert "Longitudinal Gain Report" in (output_dir / "latest.md").read_text(encoding="utf-8")
    assert routing_path.read_text(encoding="utf-8") == original_routing
    assert report.routing_table_mutated is False


def test_runs_cli_longitudinal_gain_writes_report(tmp_path) -> None:
    history_path = tmp_path / ".hermes" / "capability-history" / "history.jsonl"
    for item in [
        _record("run-1", 1, verified=False, teacher_used=True),
        _record("run-2", 2, verified=True, teacher_used=True),
        _record("run-3", 3, verified=True, teacher_used=False),
        _record("run-4", 4, verified=True, teacher_used=False),
    ]:
        _append_history(history_path, **item)

    env = {**os.environ, "PYTHONPATH": f"{Path(__file__).parents[1]}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "longitudinal-gain",
            "--history",
            str(history_path),
            "--min-samples",
            "2",
            "--window-size",
            "2",
            "--write-report",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )

    payload = json.loads(completed.stdout)
    assert payload["total_groups"] == 1
    assert payload["groups"][0]["pass_rate_delta"] == 0.5
    assert payload["routing_table_mutated"] is False
    assert (tmp_path / ".hermes" / "longitudinal-gain" / "latest.json").exists()
