from __future__ import annotations

import json
import zipfile

from feiyue_core.workflow.runs_export import export_static_runs_report
from feiyue_core.workflow.runs_export_bundle import pack_static_runs_report
from feiyue_core.workflow.runs_export_verify import verify_static_runs_report


def _write_run_evidence(root, task_id="bundle-demo"):
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


def test_pack_static_runs_report_writes_portable_zip_without_source_evidence(tmp_path) -> None:
    _write_run_evidence(tmp_path, "bundle-demo")
    exported = export_static_runs_report(tmp_path, tmp_path / "report")

    result = pack_static_runs_report(exported.index_path.parent, tmp_path / "feiyue-runs-report.zip")

    assert result.bundle_path.exists()
    assert result.entries == ["index.html", "manifest.json", "runs/bundle-demo.html"]
    with zipfile.ZipFile(result.bundle_path) as archive:
        assert archive.namelist() == result.entries
        assert ".hermes/runs/bundle-demo/run-evidence.json" not in archive.namelist()
        assert "Feiyue Run Dashboard" in archive.read("index.html").decode("utf-8")


def test_packed_static_runs_report_can_be_extracted_and_verified(tmp_path) -> None:
    _write_run_evidence(tmp_path, "bundle-demo")
    exported = export_static_runs_report(tmp_path, tmp_path / "report")
    packed = pack_static_runs_report(exported.index_path.parent, tmp_path / "feiyue-runs-report.zip")
    extract_dir = tmp_path / "unpacked"

    with zipfile.ZipFile(packed.bundle_path) as archive:
        archive.extractall(extract_dir)

    result = verify_static_runs_report(extract_dir / "manifest.json")

    assert result.valid is True
    assert result.checked_files == 3
    assert result.issues == []
