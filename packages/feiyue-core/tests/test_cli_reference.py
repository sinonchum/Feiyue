from __future__ import annotations

import subprocess
import sys


def test_runs_cli_writes_stable_cli_reference_without_secrets(tmp_path) -> None:
    output = tmp_path / "cli-reference.md"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "cli-reference",
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert str(output) in completed.stdout
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert text.startswith("# Feiyue CLI Reference")
    assert "Generated from the productized `feiyue-runs` command registry." in text
    assert "## Core evidence inspection" in text
    assert "`feiyue-runs list [--json]`" in text
    assert "`feiyue-runs review-inbox`" in text
    assert "## Approval-gated operations" in text
    assert "`feiyue-runs approve-promotion <run_id> ...`" in text
    assert "`feiyue-runs verify-production-promotion-readiness <release_id>`" in text
    assert "## Safety defaults" in text
    assert "No command in this reference requires secrets to be written into docs." in text
    forbidden = ["ghp_", "github_pat_", "AKIA", "Authorization: Bearer", "PRIVATE KEY"]
    assert not any(marker in text for marker in forbidden)
    assert "sk-" not in text.replace("task-id", "task_id").replace("task-pack", "task_pack")
