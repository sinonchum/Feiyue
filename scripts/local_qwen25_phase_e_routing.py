#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from feiyue_core.workflow.capability_feedback import CapabilityFeedbackAggregator
from feiyue_core.workflow.capability_history import CapabilityHistoryCollector
from feiyue_core.workflow.model_routing_table import ModelRoutingTableInitializer
from feiyue_core.workflow.routing_proposal import RoutingApplyGate, RoutingProposalGenerator


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _derived_smoke_payloads(phase_d: dict[str, object], *, run_id: str) -> list[dict[str, object]]:
    profile = str(phase_d.get("profile") or "local-qwen25-coder")
    model = str(phase_d.get("model") or "qwen2.5-coder:7b-instruct")
    wave9 = phase_d.get("wave9") if isinstance(phase_d.get("wave9"), dict) else {}
    real = phase_d.get("real_multi_worker") if isinstance(phase_d.get("real_multi_worker"), dict) else {}
    now = datetime.now(UTC).isoformat()
    return [
        {
            "schema_version": "feiyue.phase_e.capability_tag.v1",
            "run_id": f"{run_id}-wave9-task-pack-capability",
            "task_id": wave9.get("task_id") or f"task.{run_id}.wave9",
            "worker_profile": profile,
            "profile": profile,
            "model": model,
            "capability": "phase_e_wave9_task_pack_worker",
            "status": "verified" if wave9.get("status") == "verified" else "failed",
            "verified": wave9.get("status") == "verified",
            "provider_call_count": int(wave9.get("provider_call_count") or 0),
            "teacher_profile": None,
            "promotion_attempted": False,
            "routing_table_mutated": False,
            "source_phase_d_run_id": phase_d.get("run_id"),
            "source_evidence_path": ".hermes/phase-d-workflow-benchmarks/local-qwen25-coder-phase-d-20260615/evidence.json",
            "workflow_report": {
                "status": "verified" if wave9.get("status") == "verified" else "failed",
                "verification_passed": wave9.get("status") == "verified",
                "teacher_guidance_events": [],
                "capability": "phase_e_wave9_task_pack_worker",
                "changed_files": ["calc.py", "README.md"],
                "verification_command": "python -m pytest -q",
            },
            "dry_run_only": True,
            "written_at": now,
        },
        {
            "schema_version": "feiyue.phase_e.capability_tag.v1",
            "run_id": f"{run_id}-real-multi-worker-capability",
            "task_id": real.get("task_id") or f"task.{run_id}.real_multi_worker",
            "worker_profile": profile,
            "profile": profile,
            "model": model,
            "capability": "phase_e_real_multi_worker_worker",
            "status": "verified" if real.get("status") == "verified" else "failed",
            "verified": real.get("status") == "verified",
            "provider_call_count": int(real.get("provider_call_count") or 0),
            "teacher_profile": real.get("teacher_profile"),
            "promotion_attempted": False,
            "routing_table_mutated": False,
            "source_phase_d_run_id": phase_d.get("run_id"),
            "source_evidence_path": ".hermes/phase-d-workflow-benchmarks/local-qwen25-coder-phase-d-20260615/evidence.json",
            "workflow_report": {
                "status": "verified" if real.get("status") == "verified" else "failed",
                "verification_passed": real.get("status") == "verified",
                "teacher_guidance_events": [],
                "capability": "phase_e_real_multi_worker_worker",
                "changed_files": ["calc.py"],
                "verification_command": "python -m pytest -q",
            },
            "dry_run_only": True,
            "written_at": now,
        },
    ]


def _summary_markdown(payload: dict[str, object]) -> str:
    proposal = payload.get("routing_proposal") if isinstance(payload.get("routing_proposal"), dict) else {}
    feedback = payload.get("capability_feedback") if isinstance(payload.get("capability_feedback"), dict) else {}
    history = payload.get("capability_history") if isinstance(payload.get("capability_history"), dict) else {}
    changes = proposal.get("recommended_changes") if isinstance(proposal.get("recommended_changes"), list) else []
    lines = [
        f"# Phase E Qwen2.5-Coder Capability Tags / Routing Proposal: {payload['run_id']}",
        "",
        f"- status: {payload['status']}",
        f"- profile: {payload['profile']}",
        f"- model: {payload['model']}",
        f"- derived_capability_tags: {', '.join(payload.get('derived_capability_tags', []))}",
        f"- capability_history_total_records: {history.get('total_records')}",
        f"- feedback_total_workflow_runs: {feedback.get('total_workflow_runs')}",
        f"- proposal_id: {proposal.get('proposal_id')}",
        f"- recommended_change_count: {len(changes)}",
        f"- apply_without_approval_status: {payload.get('apply_without_approval_status')}",
        "- safety: routing_table_mutated=false, requires_human_approval=true, promotion_attempted=false, production_mutated=false",
        "",
        "## Recommended changes",
    ]
    for change in changes:
        if isinstance(change, dict):
            lines.append(f"- {change.get('profile')}: {change.get('recommended_action')} for {change.get('target_role')} — {change.get('reason')}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase E: productize local Qwen Phase D evidence into capability tags and routing proposal evidence.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--run-id", default=f"local-qwen25-coder-phase-e-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--phase-d-run-id", default="local-qwen25-coder-phase-d-20260615")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    phase_d_path = project_root / ".hermes" / "phase-d-workflow-benchmarks" / args.phase_d_run_id / "evidence.json"
    phase_d = _read_json(phase_d_path)
    if phase_d.get("status") != "verified":
        raise SystemExit(f"Phase D evidence is not verified: {phase_d_path}")

    # Create provider-free, auditable derived workflow-smoke records so existing Feiyue history/feedback tools can ingest Phase D capabilities.
    derived_tags: list[str] = []
    derived_paths: list[str] = []
    for payload in _derived_smoke_payloads(phase_d, run_id=args.run_id):
        tag = str(payload["capability"])
        derived_tags.append(tag)
        path = project_root / ".hermes" / "workflow-smokes" / str(payload["run_id"]) / "evidence.json"
        _write_json(path, payload)
        derived_paths.append(str(path))

    history = CapabilityHistoryCollector(project_root).write_report()
    feedback = CapabilityFeedbackAggregator(project_root).write_report()
    routing_path = ModelRoutingTableInitializer(project_root).initialize(overwrite=False)
    proposal = RoutingProposalGenerator(project_root).write_proposal(proposal_id=f"proposal.{args.run_id}.local-qwen25-worker")
    blocked_apply = RoutingApplyGate(project_root).apply_proposal(proposal=proposal, approval=None)

    profile = str(phase_d.get("profile") or "local-qwen25-coder")
    profile_history = history.profile_summaries.get(profile)
    profile_feedback = feedback.profile_metrics.get(profile)
    status = "proposal_ready" if proposal.requires_human_approval and not proposal.routing_table_mutated and blocked_apply.status.value == "blocked" else "failed"
    payload = {
        "schema_version": "feiyue.local_qwen25.phase_e.v1",
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "profile": profile,
        "model": str(phase_d.get("model") or "qwen2.5-coder:7b-instruct"),
        "source_phase_d_run_id": args.phase_d_run_id,
        "source_phase_d_evidence_path": str(phase_d_path),
        "derived_capability_tags": derived_tags,
        "derived_workflow_smoke_paths": derived_paths,
        "capability_history": {
            "total_records": history.total_records,
            "profile_summary": profile_history.model_dump(mode="json") if profile_history else None,
            "latest_json": str(project_root / ".hermes" / "capability-history" / "latest.json"),
            "latest_md": str(project_root / ".hermes" / "capability-history" / "latest.md"),
        },
        "capability_feedback": {
            "total_workflow_runs": feedback.total_workflow_runs,
            "profile_metrics": profile_feedback.model_dump(mode="json") if profile_feedback else None,
            "recommendations": [r.model_dump(mode="json") for r in feedback.recommendations if r.profile == profile],
            "latest_json": str(project_root / ".hermes" / "capability-feedback" / "latest.json"),
            "latest_md": str(project_root / ".hermes" / "capability-feedback" / "latest.md"),
        },
        "routing_proposal": proposal.model_dump(mode="json"),
        "routing_model_path": str(routing_path),
        "apply_without_approval_status": blocked_apply.status.value,
        "apply_without_approval_reason_codes": blocked_apply.reason_codes,
        "apply_evidence_path": blocked_apply.evidence_path,
        "safety_flags": {
            "routing_table_mutated": False,
            "requires_human_approval": True,
            "promotion_attempted": False,
            "production_mutated": False,
            "global_hermes_config_mutated": False,
        },
    }
    out_dir = project_root / ".hermes" / "phase-e-routing-proposals" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evidence.json"
    md_path = out_dir / "evidence.md"
    _write_json(json_path, payload)
    md_path.write_text(_summary_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "run_id": args.run_id,
        "status": status,
        "derived_capability_tags": derived_tags,
        "capability_history_total_records": history.total_records,
        "feedback_total_workflow_runs": feedback.total_workflow_runs,
        "routing_proposal_id": proposal.proposal_id,
        "recommended_change_count": len(proposal.recommended_changes),
        "apply_without_approval_status": blocked_apply.status.value,
        "evidence_paths": [str(json_path), str(md_path)],
    }, indent=2, ensure_ascii=False))
    return 0 if status == "proposal_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
