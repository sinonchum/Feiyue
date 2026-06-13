from __future__ import annotations

import hashlib
import json

from feiyue_core.workflow.runs_export import export_static_runs_report


def _write_run_evidence(root, task_id="m13-export-demo"):
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


def test_export_static_runs_report_writes_offline_dashboard_and_detail(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-export-demo")
    output_dir = tmp_path / "report"

    result = export_static_runs_report(tmp_path, output_dir)

    assert result.index_path == output_dir / "index.html"
    assert result.detail_paths == {"m13-export-demo": output_dir / "runs" / "m13-export-demo.html"}
    assert result.index_path.exists()
    assert result.detail_paths["m13-export-demo"].exists()

    index_html = result.index_path.read_text(encoding="utf-8")
    detail_html = result.detail_paths["m13-export-demo"].read_text(encoding="utf-8")

    assert "Feiyue Run Dashboard" in index_html
    assert 'href="runs/m13-export-demo.html"' in index_html
    assert "Feiyue Run Detail" in detail_html
    assert "Policy Decision" in detail_html
    assert "Action Evidence" in detail_html
    assert "Approval Evidence" in detail_html
    assert 'href="../index.html"' in detail_html
    assert "<pre>" not in index_html + detail_html
    assert "JSON.stringify" not in index_html + detail_html


def test_export_static_runs_report_writes_asset_catalog_page_and_manifest_entry(tmp_path) -> None:
    (tmp_path / ".hermes" / "lessons").mkdir(parents=True)
    (tmp_path / ".hermes" / "lessons" / "lesson-export.md").write_text(
        "# Exported Lesson\n\nsecret=SHOULD_NOT_LEAK\n", encoding="utf-8"
    )
    output_dir = tmp_path / "report"

    result = export_static_runs_report(tmp_path, output_dir)

    assets_path = output_dir / "assets" / "index.html"
    assert assets_path.exists()
    assets_html = assets_path.read_text(encoding="utf-8")
    assert "Feiyue Asset Catalog" in assets_html
    assert "Exported Lesson" in assets_html
    assert "SHOULD_NOT_LEAK" not in assets_html

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert any(file["path"] == "assets/index.html" for file in manifest["files"])


def test_export_static_runs_report_writes_manifest_with_hashes_and_sources(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-export-demo")
    output_dir = tmp_path / "report"

    result = export_static_runs_report(tmp_path, output_dir)

    assert result.manifest_path == output_dir / "manifest.json"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "feiyue.static_runs_report.v1"
    assert manifest["project_root"] == str(tmp_path)
    assert manifest["total_runs"] == 1
    assert manifest["generated_at"].endswith("Z")
    assert manifest["files"][0]["path"] == "index.html"
    assert manifest["files"][0]["sha256"] == hashlib.sha256(result.index_path.read_bytes()).hexdigest()
    assert manifest["runs"] == [
        {
            "task_id": "m13-export-demo",
            "detail_path": "runs/m13-export-demo.html",
            "detail_sha256": hashlib.sha256(result.detail_paths["m13-export-demo"].read_bytes()).hexdigest(),
            "source_evidence_path": ".hermes/runs/m13-export-demo/run-evidence.json",
            "source_evidence_sha256": hashlib.sha256(
                (tmp_path / ".hermes" / "runs" / "m13-export-demo" / "run-evidence.json").read_bytes()
            ).hexdigest(),
        }
    ]


def test_export_static_runs_report_handles_empty_runs(tmp_path) -> None:
    output_dir = tmp_path / "report"

    result = export_static_runs_report(tmp_path, output_dir)

    assert result.index_path.exists()
    assert result.detail_paths == {}
    assert "No run evidence found." in result.index_path.read_text(encoding="utf-8")
