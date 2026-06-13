from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_provider_free_example_readme_documents_copy_paste_commands() -> None:
    readme = Path(__file__).resolve().parents[3] / "examples" / "provider-free-smoke" / "README.md"

    content = readme.read_text(encoding="utf-8")

    assert "python -m feiyue_core.examples.provider_free_smoke" in content
    assert "--root" in content
    assert "--out" in content
    assert "--bundle" in content
    assert "Expected exit code: `0`" in content
    assert "PROVIDER_FREE_EXAMPLE_SMOKE_OK" in content


def test_provider_free_example_runs_workflow_and_exports_bundle(tmp_path: Path) -> None:
    from feiyue_core.examples.provider_free_smoke import run_provider_free_example

    root = tmp_path / "example-project"
    out = tmp_path / "static-report"
    bundle = tmp_path / "static-report.zip"

    result = run_provider_free_example(root=root, out=out, bundle=bundle)

    assert result.task_id == "m14-provider-free-example-smoke"
    assert result.workflow_status == "verified"
    assert result.promotion_status == "promoted"
    assert result.initial_verify is True
    assert result.extracted_verify is True
    assert result.bundle_path == bundle
    assert result.run_evidence_path == root / ".hermes" / "runs" / result.task_id / "run-evidence.json"
    assert result.run_evidence_path.exists()
    assert result.handoff_summary_path.exists()
    assert "# Fallback Handoff Summary" in result.handoff_summary_path.read_text(encoding="utf-8")
    assert (out / "index.html").exists()
    assert (out / "manifest.json").exists()
    assert bundle.exists()


def test_provider_free_example_cli_smoke(tmp_path: Path) -> None:
    root = tmp_path / "example-project"
    out = tmp_path / "static-report"
    bundle = tmp_path / "static-report.zip"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.examples.provider_free_smoke",
            "--root",
            str(root),
            "--out",
            str(out),
            "--bundle",
            str(bundle),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "PROVIDER_FREE_EXAMPLE_SMOKE_OK" in completed.stdout
    assert "task_id: m14-provider-free-example-smoke" in completed.stdout
    assert "initial_verify: True" in completed.stdout
    assert "extracted_verify: True" in completed.stdout
    assert bundle.exists()
