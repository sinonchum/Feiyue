import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.asset_reuse_smoke import AssetReuseSmokeHarness


def _write_promoted_lesson(root: Path, name: str = "lesson-live-b.md") -> Path:
    lesson_path = root / ".hermes" / "lessons" / name
    lesson_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_path.write_text(
        "\n".join(
            [
                "# Live B teacher retry lesson: task-python-fix",
                "",
                "- Source run: live-b-1",
                "- Initial verifier failure: expected 42 but got 41",
                "- Teacher guidance: use the corrected boundary condition before retrying.",
                "- Verified by: python -m pytest -q",
                "",
                "Prevention rule: when verifier feedback shows expected 42 but got 41, apply the corrected boundary condition before any retry.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return lesson_path


def test_asset_reuse_harness_loads_project_local_lesson_and_prevents_known_error(tmp_path) -> None:
    lesson_path = _write_promoted_lesson(tmp_path)
    routing_path = tmp_path / ".hermes" / "model-routing.yaml"
    routing_path.write_text("routes:\n  worker:\n    primary: student-a\n", encoding="utf-8")

    report = AssetReuseSmokeHarness(tmp_path).run(
        run_id="reuse-1",
        lesson_path=lesson_path,
        comparable_task_id="task-python-fix-repeat",
        write_report=True,
    )

    assert report.run_id == "reuse-1"
    assert report.lesson_loaded is True
    assert report.lesson_path == ".hermes/lessons/lesson-live-b.md"
    assert report.comparable_task_id == "task-python-fix-repeat"
    assert report.error_prevented is True
    assert report.teacher_call_required is False
    assert report.retry_count == 0
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.global_hermes_config_mutated is False
    assert report.before_metrics is not None
    assert report.after_metrics is not None
    assert report.after_metrics["teacher_used"] is False
    assert report.after_metrics["verified"] is True
    output_dir = tmp_path / ".hermes" / "asset-reuse" / "reuse-1"
    evidence = json.loads((output_dir / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["error_prevented"] is True
    assert evidence["teacher_call_required"] is False
    assert "Asset Reuse Smoke" in (output_dir / "report.md").read_text(encoding="utf-8")
    assert routing_path.read_text(encoding="utf-8") == "routes:\n  worker:\n    primary: student-a\n"


def test_asset_reuse_harness_fails_closed_for_non_project_local_lesson(tmp_path) -> None:
    outside = tmp_path.parent / "outside-lesson.md"
    outside.write_text("Prevention rule: avoid expected 42 but got 41\n", encoding="utf-8")

    report = AssetReuseSmokeHarness(tmp_path).run(
        run_id="reuse-blocked",
        lesson_path=outside,
        comparable_task_id="task-python-fix-repeat",
        write_report=False,
    )

    assert report.lesson_loaded is False
    assert report.error_prevented is False
    assert report.teacher_call_required is True
    assert report.retry_count == 1
    assert report.dry_run_only is True
    assert report.promotion_attempted is False
    assert report.global_hermes_config_mutated is False
    assert report.reason_codes[0] == "lesson_not_project_local"


def test_runs_cli_asset_reuse_smoke_writes_evidence(tmp_path) -> None:
    lesson_path = _write_promoted_lesson(tmp_path)
    env = {**os.environ, "PYTHONPATH": f"{Path(__file__).parents[1]}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "asset-reuse-smoke",
            "--run-id",
            "reuse-cli",
            "--lesson-path",
            str(lesson_path),
            "--write-report",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )

    payload = json.loads(completed.stdout)
    assert payload["run_id"] == "reuse-cli"
    assert payload["lesson_loaded"] is True
    assert payload["comparable_task_id"] == "asset-reuse-smoke-comparable"
    assert payload["error_prevented"] is True
    assert payload["teacher_call_required"] is False
    assert payload["dry_run_only"] is True
    assert payload["promotion_attempted"] is False
    assert payload["global_hermes_config_mutated"] is False
    assert (tmp_path / ".hermes" / "asset-reuse" / "reuse-cli" / "evidence.json").exists()
