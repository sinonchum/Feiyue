import json
import subprocess
import sys

from feiyue_core.workflow.capability_feedback import CapabilityFeedbackAggregator, FeedbackRecommendationAction


def _write_smoke(root, run_id, *, worker_profile, status, provider_call_count=1, teacher_guidance_count=0):
    smoke_dir = root / ".hermes" / "workflow-smokes" / run_id
    smoke_dir.mkdir(parents=True, exist_ok=True)
    (smoke_dir / "evidence.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": run_id,
                "status": status,
                "worker_profile": worker_profile,
                "teacher_profile": "strong" if teacher_guidance_count else None,
                "provider_call_count": provider_call_count,
                "reason_codes": ["test_fixture"],
                "dry_run_only": True,
                "promotion_attempted": False,
                "source_repo_clean": True,
                "workflow_report": {
                    "task_id": run_id,
                    "status": status,
                    "changed_files": ["calc.py"],
                    "verification_passed": status == "verified",
                    "promotion_ready": status == "verified",
                    "source_repo_clean": True,
                    "sandbox_removed": True,
                    "verification_command": "python -m pytest -q",
                    "attempt_count": 1 if not teacher_guidance_count else 2,
                    "teacher_guidance_events": [{} for _ in range(teacher_guidance_count)],
                    "attempt_evidence": [],
                    "execution_performed": True,
                    "retry_performed": bool(teacher_guidance_count),
                },
                "stdout_redacted": [],
                "stderr_redacted": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_promotion(root, run_id, *, status="promoted"):
    promotion_dir = root / ".hermes" / "workflow-promotions" / run_id
    promotion_dir.mkdir(parents=True, exist_ok=True)
    (promotion_dir / "promotion-evidence.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": run_id,
                "status": status,
                "target_branch": "feiyue/demo",
                "approval_applies": status == "promoted",
                "promotion_attempted": True,
                "reason_codes": ["promotion_approval_applies"],
                "source_repo_clean": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_capability_feedback_aggregates_workflow_and_promotion_evidence(tmp_path) -> None:
    _write_smoke(tmp_path, "run-verified", worker_profile="weak-a", status="verified")
    _write_promotion(tmp_path, "run-verified", status="promoted")
    _write_smoke(tmp_path, "run-needs-teacher", worker_profile="weak-a", status="needs_teacher", provider_call_count=3, teacher_guidance_count=1)
    _write_smoke(tmp_path, "run-blocked", worker_profile="weak-b", status="blocked")

    report = CapabilityFeedbackAggregator(tmp_path).build_report()

    weak_a = report.profile_metrics["weak-a"]
    assert weak_a.workflow_runs == 2
    assert weak_a.verified_runs == 1
    assert weak_a.needs_teacher_runs == 1
    assert weak_a.teacher_guidance_events == 1
    assert weak_a.promoted_runs == 1
    assert weak_a.verification_rate == 0.5
    assert weak_a.promotion_rate == 0.5
    weak_b = report.profile_metrics["weak-b"]
    assert weak_b.blocked_runs == 1
    assert report.total_workflow_runs == 3
    assert report.routing_table_mutated is False


def test_capability_feedback_recommends_audit_only_routing_actions(tmp_path) -> None:
    _write_smoke(tmp_path, "ok-1", worker_profile="steady", status="verified")
    _write_smoke(tmp_path, "ok-2", worker_profile="steady", status="verified")
    _write_promotion(tmp_path, "ok-2", status="promoted")
    _write_smoke(tmp_path, "bad-1", worker_profile="fragile", status="needs_teacher", teacher_guidance_count=1)
    _write_smoke(tmp_path, "bad-2", worker_profile="fragile", status="blocked")

    report = CapabilityFeedbackAggregator(tmp_path).build_report()

    recommendations = {item.profile: item for item in report.recommendations}
    assert recommendations["steady"].action is FeedbackRecommendationAction.CONSIDER_PROMOTION
    assert "verification_rate=1.00" in recommendations["steady"].reason
    assert recommendations["fragile"].action is FeedbackRecommendationAction.KEEP_REVIEW
    assert "teacher_or_blocked_rate=1.00" in recommendations["fragile"].reason
    assert all(item.mutates_routing_table is False for item in report.recommendations)


def test_runs_cli_capability_feedback_writes_report_without_mutating_routing_table(tmp_path) -> None:
    _write_smoke(tmp_path, "ok-1", worker_profile="steady", status="verified")
    routing_path = tmp_path / ".hermes" / "model-routing.yaml"
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    original_routing = "routes:\n  worker:\n    primary: steady\n"
    routing_path.write_text(original_routing, encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "capability-feedback", "--write-report"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["routing_table_mutated"] is False
    assert payload["profile_metrics"]["steady"]["verified_runs"] == 1
    assert routing_path.read_text(encoding="utf-8") == original_routing
    assert (tmp_path / ".hermes" / "capability-feedback" / "latest.json").exists()
    assert (tmp_path / ".hermes" / "capability-feedback" / "latest.md").exists()
