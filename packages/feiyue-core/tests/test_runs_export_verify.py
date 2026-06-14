from __future__ import annotations

import json

from feiyue_core.workflow.runs_export import export_static_runs_report
from feiyue_core.workflow.runs_export_verify import verify_static_runs_report


def _write_run_evidence(root, task_id="verify-demo"):
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


def test_verify_static_runs_report_accepts_matching_manifest(tmp_path) -> None:
    _write_run_evidence(tmp_path, "verify-demo")
    exported = export_static_runs_report(tmp_path, tmp_path / "report")

    result = verify_static_runs_report(exported.manifest_path)

    assert result.valid is True
    assert result.checked_files == 5
    assert result.issues == []


def test_verify_static_runs_report_rejects_modified_detail_html(tmp_path) -> None:
    _write_run_evidence(tmp_path, "verify-demo")
    exported = export_static_runs_report(tmp_path, tmp_path / "report")
    exported.detail_paths["verify-demo"].write_text("tampered", encoding="utf-8")

    result = verify_static_runs_report(exported.manifest_path)

    assert result.valid is False
    assert result.checked_files == 5
    assert result.issues == [
        "sha256 mismatch: runs/verify-demo.html",
    ]


def test_verify_static_runs_report_rejects_modified_source_evidence(tmp_path) -> None:
    _write_run_evidence(tmp_path, "verify-demo")
    exported = export_static_runs_report(tmp_path, tmp_path / "report")
    evidence = tmp_path / ".hermes" / "runs" / "verify-demo" / "run-evidence.json"
    evidence.write_text("{}", encoding="utf-8")

    result = verify_static_runs_report(exported.manifest_path)

    assert result.valid is False
    assert result.issues == [
        "source evidence sha256 mismatch: .hermes/runs/verify-demo/run-evidence.json",
    ]
