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


def _write_run_evidence(root, task_id="m12-cli-demo"):
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
                "report_paths": {"execution_report": "execution-report.md", "execution_json": "execution-report.json"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_dir


def test_runs_cli_lists_persisted_run_ids(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m12-cli-demo")
    _write_run_evidence(tmp_path, "m12-cli-second")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "list"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout.splitlines() == ["m12-cli-demo", "m12-cli-second"]


def test_runs_cli_shows_run_evidence_json(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m12-cli-demo")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "show", "m12-cli-demo"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["task_id"] == "m12-cli-demo"
    assert payload["next_safe_action"] == "request_human_approval"
    assert payload["approval_exists"] is False


def test_runs_cli_renders_fallback_handoff_summary(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m12-cli-demo")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "handoff", "m12-cli-demo"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "# Fallback Handoff Summary" in completed.stdout
    assert "- task_id: m12-cli-demo" in completed.stdout
    assert "## Approval Evidence" in completed.stdout
    assert "- approval_exists: False" in completed.stdout


def test_runs_cli_missing_run_exits_nonzero_with_stable_error(tmp_path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "show", "missing-task"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "Run evidence index not found" in completed.stderr
    assert "missing-task" in completed.stderr


def test_runs_cli_lists_catalog_summary_as_json(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-cli-catalog")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "list", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["total_runs"] == 1
    assert payload["safe_to_retry_count"] == 0
    assert payload["next_action_counts"] == {"request_human_approval": 1}
    assert payload["runs"][0]["task_id"] == "m13-cli-catalog"
    assert payload["runs"][0]["approval_exists"] is False
