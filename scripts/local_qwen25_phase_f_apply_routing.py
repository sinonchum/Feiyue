#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from feiyue_core.workflow.model_routing_table import ModelRoutingTable
from feiyue_core.workflow.routing_proposal import (
    RoutingApplyGate,
    RoutingApplyStatus,
    RoutingProposalApproval,
    read_routing_proposal,
    recommended_changes_hash,
    write_routing_proposal_approval,
)


def _sha256_text(text: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _markdown(payload: dict[str, object]) -> str:
    before = payload.get("routing_before") if isinstance(payload.get("routing_before"), dict) else {}
    after = payload.get("routing_after") if isinstance(payload.get("routing_after"), dict) else {}
    apply_result = payload.get("apply_result") if isinstance(payload.get("apply_result"), dict) else {}
    return "\n".join(
        [
            f"# Phase F Approved Routing Apply: {payload['run_id']}",
            "",
            f"- status: {payload['status']}",
            f"- proposal_id: {payload['proposal_id']}",
            f"- approval_id: {payload['approval_id']}",
            f"- approved_by: {payload['approved_by']}",
            f"- worker_before: {before.get('worker_primary')}",
            f"- worker_after: {after.get('worker_primary')}",
            f"- apply_status: {apply_result.get('status')}",
            f"- routing_table_mutated: {apply_result.get('routing_table_mutated')}",
            f"- applied_profiles: {', '.join(apply_result.get('applied_profiles', []))}",
            "- scope: project-local .hermes/model-routing.yaml only",
            "- safety: global_hermes_config_mutated=false, production_mutated=false, external_pr_created=false, deploy_performed=false",
            "",
            "## Reason codes",
            *[f"- {code}" for code in apply_result.get("reason_codes", [])],
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase F: simulated human approval and project-local apply of reviewed routing proposal.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--run-id", default=f"local-qwen25-coder-phase-f-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--proposal-id", default="proposal.local-qwen25-coder-phase-e-20260615.local-qwen25-worker")
    parser.add_argument("--approved-by", default="simon-phase-f-simulated-human-approval")
    parser.add_argument("--approval-id", default=None)
    parser.add_argument("--reason", default="Simon requested Phase F: apply reviewed local-qwen25-coder worker routing proposal to project-local routing table only.")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    proposal = read_routing_proposal(project_root, args.proposal_id)
    routing_path = project_root / ".hermes" / "model-routing.yaml"
    routing_before_text = routing_path.read_text(encoding="utf-8")
    routing_before_hash = _sha256_text(routing_before_text)
    if routing_before_hash != proposal.current_routing_hash:
        raise SystemExit(
            "current routing table hash does not match proposal; refusing stale apply: "
            f"current={routing_before_hash}, proposal={proposal.current_routing_hash}"
        )
    before_table = ModelRoutingTable.parse_yaml(routing_before_text)
    before_worker = before_table.routes["worker"].primary

    proposal_dir = project_root / ".hermes" / "routing-proposals" / proposal.proposal_id
    previous_apply = proposal_dir / "apply-evidence.json"
    preserved_blocked_apply_path = None
    if previous_apply.exists():
        preserved_blocked_apply_path = proposal_dir / f"apply-evidence.before-{args.run_id}.json"
        shutil.copy2(previous_apply, preserved_blocked_apply_path)

    approval_id = args.approval_id or f"approval.{args.run_id}.simon"
    approval = RoutingProposalApproval(
        approval_id=approval_id,
        approved_by=args.approved_by,
        proposal_id=proposal.proposal_id,
        approved_action="apply_reviewed_routing_proposal",
        source_feedback_hash=proposal.source_feedback_hash,
        current_routing_hash=proposal.current_routing_hash,
        recommended_changes_hash=recommended_changes_hash(proposal.recommended_changes),
        approved_at=datetime.now(UTC).isoformat(),
        reason=args.reason,
    )
    approval_path = write_routing_proposal_approval(approval, project_root)
    apply_result = RoutingApplyGate(project_root).apply_proposal(proposal=proposal, approval=approval)

    routing_after_text = routing_path.read_text(encoding="utf-8")
    after_table = ModelRoutingTable.parse_yaml(routing_after_text)
    after_worker = after_table.routes["worker"].primary
    expected_profiles = [change.profile for change in proposal.recommended_changes if change.recommended_action == "consider_promotion" and change.target_role == "worker"]
    expected_worker = expected_profiles[-1] if expected_profiles else before_worker
    status = "applied" if apply_result.status is RoutingApplyStatus.APPLIED and after_worker == expected_worker else "failed"

    payload = {
        "schema_version": "feiyue.local_qwen25.phase_f.v1",
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "proposal_id": proposal.proposal_id,
        "approval_id": approval.approval_id,
        "approved_by": approval.approved_by,
        "approval_path": str(approval_path),
        "preserved_previous_apply_evidence_path": str(preserved_blocked_apply_path) if preserved_blocked_apply_path else None,
        "routing_model_path": str(routing_path),
        "routing_before": {
            "hash": routing_before_hash,
            "worker_primary": before_worker,
            "text": routing_before_text,
        },
        "routing_after": {
            "hash": _sha256_text(routing_after_text),
            "worker_primary": after_worker,
            "text": routing_after_text,
        },
        "recommended_changes": [change.model_dump(mode="json") for change in proposal.recommended_changes],
        "apply_result": apply_result.model_dump(mode="json"),
        "safety_flags": {
            "project_local_routing_table_mutated": apply_result.routing_table_mutated,
            "global_hermes_config_mutated": False,
            "production_mutated": False,
            "external_pr_created": False,
            "deploy_performed": False,
            "promotion_attempted": False,
        },
    }
    out_dir = project_root / ".hermes" / "phase-f-routing-apply" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evidence.json"
    md_path = out_dir / "evidence.md"
    _write_json(json_path, payload)
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "status": status,
                "proposal_id": proposal.proposal_id,
                "approval_id": approval.approval_id,
                "worker_before": before_worker,
                "worker_after": after_worker,
                "routing_table_mutated": apply_result.routing_table_mutated,
                "apply_status": apply_result.status.value,
                "evidence_paths": [str(json_path), str(md_path)],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if status == "applied" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
