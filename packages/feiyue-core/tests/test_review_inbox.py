from __future__ import annotations

import json
import subprocess
import sys

from feiyue_core.workflow.review_inbox import ReviewInbox


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_review_inbox_aggregates_pending_local_evidence_without_mutation(tmp_path) -> None:
    routing_proposal = tmp_path / ".hermes" / "routing-proposals" / "route-1" / "proposal.json"
    _write_json(
        routing_proposal,
        {
            "proposal_id": "route-1",
            "requires_human_approval": True,
            "routing_table_mutated": False,
        },
    )
    applied_routing = tmp_path / ".hermes" / "routing-proposals" / "route-done" / "proposal.json"
    _write_json(applied_routing, {"proposal_id": "route-done"})
    _write_json(applied_routing.parent / "approval.json", {"approval_id": "approval-route-done"})
    _write_json(applied_routing.parent / "apply-evidence.json", {"proposal_id": "route-done", "status": "applied"})

    smoke = tmp_path / ".hermes" / "workflow-smokes" / "dry-1" / "evidence.json"
    _write_json(
        smoke,
        {
            "run_id": "dry-1",
            "task_id": "task-1",
            "status": "verified",
            "dry_run_only": True,
            "promotion_attempted": False,
        },
    )
    blocked_promotion = tmp_path / ".hermes" / "workflow-promotions" / "dry-blocked" / "promotion-evidence.json"
    _write_json(
        tmp_path / ".hermes" / "workflow-smokes" / "dry-blocked" / "evidence.json",
        {
            "run_id": "dry-blocked",
            "task_id": "task-blocked",
            "status": "verified",
            "dry_run_only": True,
            "promotion_attempted": False,
        },
    )
    _write_json(blocked_promotion, {"run_id": "dry-blocked", "status": "blocked", "reason_codes": ["missing_promotion_approval"]})

    plan = tmp_path / ".hermes" / "multi-worker-plans" / "plan-1" / "plan.json"
    _write_json(plan, {"plan_id": "plan-1", "task_id": "task-plan", "route": {"status": "selected"}})
    plan_approved = tmp_path / ".hermes" / "multi-worker-plans" / "plan-2" / "plan.json"
    _write_json(plan_approved, {"plan_id": "plan-2", "task_id": "task-plan-2", "route": {"status": "selected"}})
    _write_json(plan_approved.parent / "approval.json", {"authorization_id": "auth-plan-2"})

    asset = tmp_path / ".hermes" / "asset-proposals" / "asset-1" / "proposal.json"
    _write_json(asset, {"proposal_id": "asset-1", "status": "review_required", "proposal": {"source_task_id": "task-a"}})
    reviewed_asset = tmp_path / ".hermes" / "asset-proposals" / "asset-reviewed" / "proposal.json"
    _write_json(reviewed_asset, {"proposal_id": "asset-reviewed", "status": "approved"})

    before = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}

    summary = ReviewInbox(tmp_path).summary()

    after = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before
    assert summary.mutates_state is False
    assert [item.mutates_state for item in summary.items] == [False] * len(summary.items)

    by_key = {(item.item_type, item.item_id): item for item in summary.items}
    assert by_key[("routing_proposal", "route-1")].status == "pending_approval"
    assert by_key[("workflow_promotion", "dry-1")].recommended_action == "review_and_create_promotion_approval"
    assert by_key[("workflow_promotion", "dry-blocked")].status == "blocked_promotion"
    assert by_key[("multi_worker_plan", "plan-1")].status == "pending_approval"
    assert by_key[("multi_worker_plan", "plan-2")].status == "pending_run"
    assert by_key[("asset_proposal", "asset-1")].status == "review_required"
    assert ("routing_proposal", "route-done") not in by_key
    assert ("asset_proposal", "asset-reviewed") not in by_key


def test_review_inbox_cli_outputs_json(tmp_path) -> None:
    _write_json(
        tmp_path / ".hermes" / "routing-proposals" / "route-cli" / "proposal.json",
        {"proposal_id": "route-cli", "requires_human_approval": True},
    )

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "review-inbox", "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["mutates_state"] is False
    assert payload["items"][0]["item_type"] == "routing_proposal"
    assert payload["items"][0]["item_id"] == "route-cli"
    assert payload["items"][0]["mutates_state"] is False
