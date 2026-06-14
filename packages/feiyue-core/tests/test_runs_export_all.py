from __future__ import annotations

import json
import zipfile

from feiyue_core.workflow.runs_export_all import export_static_runs_report_all


def _write_run_evidence(root, task_id="all-demo"):
    run_dir = root / ".hermes" / "runs" / task_id
    run_dir.mkdir(parents=True)
    (run_dir / "run-evidence.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "status": "blocked",
                "policy_action": "escalate",
                "policy_reason": "high_risk_operation",
                "execution_performed": False,
                "retry_performed": False,
                "promotion_status": None,
                "promotion_side_effect_performed": None,
                "approval_exists": False,
                "approval_id": None,
                "approval_approver": None,
                "approval_action": None,
                "approval_applies": False,
                "safe_to_retry": False,
                "next_safe_action": "request_human_approval",
                "report_paths": {"execution_report": "execution-report.md"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_export_static_runs_report_all_exports_verifies_bundles_and_verifies_extracted(tmp_path) -> None:
    _write_run_evidence(tmp_path, "all-demo")
    output_dir = tmp_path / "report"
    bundle_path = tmp_path / "report.zip"

    result = export_static_runs_report_all(tmp_path, output_dir, bundle_path)

    assert result.report.index_path == output_dir / "index.html"
    assert result.report.manifest_path == output_dir / "manifest.json"
    assert result.initial_verification.valid is True
    assert result.bundle.bundle_path == bundle_path
    assert result.bundle.entries == [
        "index.html",
        "manifest.json",
        "assets/index.html",
        "review-inbox/index.html",
        "runs/all-demo.html",
    ]
    assert result.extracted_verification.valid is True
    assert result.extracted_dir.exists()
    assert (result.extracted_dir / "manifest.json").exists()
    with zipfile.ZipFile(bundle_path) as archive:
        assert archive.namelist() == result.bundle.entries


def test_export_static_runs_report_all_replaces_stale_extraction_directory(tmp_path) -> None:
    _write_run_evidence(tmp_path, "all-demo")
    output_dir = tmp_path / "report"
    bundle_path = tmp_path / "report.zip"

    result = export_static_runs_report_all(tmp_path, output_dir, bundle_path)
    stale_file = result.extracted_dir / "stale.txt"
    stale_file.write_text("stale", encoding="utf-8")

    second_result = export_static_runs_report_all(tmp_path, output_dir, bundle_path)

    assert second_result.extracted_verification.valid is True
    assert second_result.initial_verification.valid is True
    assert not stale_file.exists()
