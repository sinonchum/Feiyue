import json
import subprocess
import sys


def test_interruption_demo_cli_outputs_recovery_summary_json(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.runtime.interruption_simulation",
            "--root",
            str(tmp_path / "demo"),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["pending_operations"] == []
    assert payload["warnings"] == []
    assert payload["next_safe_action"] == "continue with next planned step"
    assert payload["verified_count"] == 3
    assert payload["file_exists"] is True
    assert payload["artifact_exists"] is True
    assert "Pending / unknown operations" in payload["recovery_prompt"]
