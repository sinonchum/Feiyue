from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_live_b_evidence(root: Path, *, run_id: str = "live-b-demo") -> Path:
    evidence_dir = root / ".hermes" / "multi-worker-workflows" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "run_id": run_id,
        "task_id": "task.live-b.teacher-retry",
        "plan_id": "plan.live-b",
        "status": "verified",
        "worker_profile": "feiyue-weak-deepseek-flash",
        "teacher_profile": "feiyue-strong-gpt55",
        "provider_call_count": 3,
        "dry_run_only": True,
        "promotion_attempted": False,
        "global_hermes_config_mutated": False,
        "retry_performed": True,
        "teacher_guidance_events": [
            {
                "request_id": "teacher-request-task.live-b.teacher-retry-1",
                "attempt_index": 2,
                "trigger": "verifier_failed",
                "guidance": "Replace the subtraction in calc.add with addition so it returns a + b.",
                "source_bug_dossier_task_id": "task.live-b.teacher-retry",
            }
        ],
        "workflow_report": {
            "task_id": "task.live-b.teacher-retry",
            "status": "verified",
            "changed_files": ["calc.py"],
            "verification_passed": True,
            "promotion_ready": True,
            "source_repo_clean": True,
            "sandbox_removed": True,
            "verification_command": "python -m pytest -q",
            "attempt_count": 2,
            "retry_performed": True,
            "attempt_evidence": [
                {
                    "attempt_index": 1,
                    "changed_files": ["calc.py"],
                    "verification_command": "python -m pytest -q",
                    "verification_passed": False,
                    "failure_reason": "assert -1 == 3",
                    "teacher_request_id": None,
                },
                {
                    "attempt_index": 2,
                    "changed_files": ["calc.py"],
                    "verification_command": "python -m pytest -q",
                    "verification_passed": True,
                    "failure_reason": None,
                    "teacher_request_id": "teacher-request-task.live-b.teacher-retry-1",
                },
            ],
            "teacher_guidance_events": [
                {
                    "request_id": "teacher-request-task.live-b.teacher-retry-1",
                    "attempt_index": 2,
                    "trigger": "verifier_failed",
                    "guidance": "Replace the subtraction in calc.add with addition so it returns a + b.",
                    "source_bug_dossier_task_id": "task.live-b.teacher-retry",
                }
            ],
        },
    }
    path = evidence_dir / "evidence.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return path


def test_live_asset_loop_builds_review_required_proposal_from_teacher_retry_evidence(tmp_path: Path) -> None:
    _write_live_b_evidence(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "curator-live-proposal",
            "--run-id",
            "live-b-demo",
            "--proposal-id",
            "asset-live-b-demo",
            "--write-proposal",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["proposal_id"] == "asset-live-b-demo"
    assert payload["status"] == "review_required"
    assert payload["source_task_id"] == "task.live-b.teacher-retry"
    assert [patch["asset_type"] for patch in payload["patches"]] == ["lesson", "regression_eval", "task_template"]
    assert all("live-b-demo" in patch["source_ids"] for patch in payload["patches"])
    assert "Replace the subtraction" in payload["patches"][0]["proposed_content"]
    proposal_path = tmp_path / ".hermes" / "asset-proposals" / "asset-live-b-demo" / "proposal.json"
    assert proposal_path.exists()
    persisted = json.loads(proposal_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "review_required"
    assert persisted["provenance"]["source_ids"]


def test_live_asset_loop_approve_and_promote_writes_project_local_assets(tmp_path: Path) -> None:
    _write_live_b_evidence(tmp_path)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "curator-live-proposal",
            "--run-id",
            "live-b-demo",
            "--proposal-id",
            "asset-live-b-demo",
            "--write-proposal",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "promote-curator-asset",
            "--proposal-id",
            "asset-live-b-demo",
            "--reviewer",
            "Simon",
            "--reason",
            "Approve project-local lesson from verified Live B teacher retry evidence.",
            "--rollback-ref",
            "rollback-live-b-demo",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["promoted"] is True
    assert payload["reason_codes"] == []
    assert payload["target_path"] == ".hermes/lessons/asset-live-b-demo.md"
    promoted = tmp_path / payload["target_path"]
    assert promoted.exists()
    content = promoted.read_text(encoding="utf-8")
    assert "Live B teacher retry lesson" in content
    assert "Replace the subtraction" in content
    record = json.loads((tmp_path / ".hermes" / "asset-proposals" / "asset-live-b-demo" / "proposal.json").read_text())
    assert record["status"] == "promoted"


def test_live_asset_loop_blocks_non_verified_or_promoting_evidence(tmp_path: Path) -> None:
    evidence_path = _write_live_b_evidence(tmp_path, run_id="bad-live-b")
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["status"] = "blocked"
    payload["promotion_attempted"] = True
    evidence_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "curator-live-proposal",
            "--run-id",
            "bad-live-b",
            "--proposal-id",
            "asset-bad-live-b",
            "--write-proposal",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "live asset loop requires verified dry-run evidence" in completed.stderr
    assert not (tmp_path / ".hermes" / "asset-proposals" / "asset-bad-live-b").exists()
