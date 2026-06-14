"""Curator live-asset loop from verified multi-worker teacher-retry evidence.

This module turns a verified Live B workflow evidence record into a
review-required distillation proposal, then delegates explicit review/promotion
state changes to the existing project-local AssetPromotionStore.  It is
provider-free and writes only under the caller's project-local .hermes tree.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from feiyue_core.curation.asset_promotion import AssetPromotionStore, PromotionEvidence
from feiyue_core.curation.distillation_proposal import DistillationProposal, ProposalPatch, build_distillation_proposal


class CuratorLiveAssetLoopError(RuntimeError):
    """Raised when live evidence cannot be safely distilled."""


def live_asset_proposal_from_multi_worker_run(
    *,
    project_root: str | Path,
    run_id: str,
    proposal_id: str,
    write_proposal: bool = False,
) -> DistillationProposal:
    """Build a review-required proposal from verified Live B evidence.

    The gate is deliberately narrow: evidence must be verified, dry-run only,
    non-promoting, retry-backed, teacher-guided, and verifier-backed.  Anything
    else is rejected before proposal persistence.
    """

    root = Path(project_root)
    evidence = _read_multi_worker_evidence(root, run_id)
    _assert_verified_teacher_retry_evidence(evidence)
    proposal = _build_proposal(evidence=evidence, run_id=run_id, proposal_id=proposal_id)
    if write_proposal:
        AssetPromotionStore(root).persist_proposal(
            proposal,
            provenance={
                "source_trace_ids": [run_id],
                "teacher_refs": [event.get("request_id") for event in evidence.get("teacher_guidance_events", []) if event.get("request_id")],
                "verifier_refs": [evidence.get("workflow_report", {}).get("verification_command")],
            },
        )
    return proposal


def approve_and_promote_curator_asset(
    *,
    project_root: str | Path,
    proposal_id: str,
    reviewer: str,
    reason: str,
    rollback_ref: str,
    patch_index: int = 0,
) -> PromotionEvidence:
    """Approve and promote one proposal patch into project-local .hermes assets."""

    store = AssetPromotionStore(project_root)
    decided_at = datetime.now(UTC).isoformat()
    store.approve(proposal_id, reviewer=reviewer, reason=reason, decided_at=decided_at)
    return store.promote(
        proposal_id,
        reviewer=reviewer,
        reason=reason,
        decided_at=decided_at,
        rollback_ref=rollback_ref,
        patch_index=patch_index,
    )


def _read_multi_worker_evidence(root: Path, run_id: str) -> dict[str, Any]:
    path = root / ".hermes" / "multi-worker-workflows" / run_id / "evidence.json"
    if not path.exists():
        raise CuratorLiveAssetLoopError(f"multi-worker workflow evidence not found for run_id: {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_verified_teacher_retry_evidence(evidence: dict[str, Any]) -> None:
    workflow = evidence.get("workflow_report") or {}
    attempt_evidence = workflow.get("attempt_evidence") or []
    teacher_events = evidence.get("teacher_guidance_events") or workflow.get("teacher_guidance_events") or []
    first_failed = bool(attempt_evidence) and attempt_evidence[0].get("verification_passed") is False
    final_passed = bool(attempt_evidence) and attempt_evidence[-1].get("verification_passed") is True
    if not (
        evidence.get("status") == "verified"
        and evidence.get("dry_run_only") is True
        and evidence.get("promotion_attempted") is False
        and evidence.get("global_hermes_config_mutated") is False
        and evidence.get("retry_performed") is True
        and workflow.get("verification_passed") is True
        and workflow.get("source_repo_clean") is True
        and first_failed
        and final_passed
        and teacher_events
    ):
        raise CuratorLiveAssetLoopError(
            "live asset loop requires verified dry-run evidence with teacher-guided retry and no promotion/global mutation"
        )


def _build_proposal(*, evidence: dict[str, Any], run_id: str, proposal_id: str) -> DistillationProposal:
    workflow = evidence["workflow_report"]
    task_id = str(evidence["task_id"])
    teacher_events = evidence.get("teacher_guidance_events") or workflow.get("teacher_guidance_events") or []
    guidance = str(teacher_events[0].get("guidance", "Use teacher guidance to repair verifier failure."))
    failure = str((workflow.get("attempt_evidence") or [{}])[0].get("failure_reason") or "Verifier failed before teacher retry.")
    verifier = str(workflow.get("verification_command", "python -m pytest -q"))
    changed_files = ", ".join(str(path) for path in workflow.get("changed_files", [])) or "unknown files"
    source_ids = [run_id, task_id, str(teacher_events[0].get("request_id", "teacher-guidance"))]
    lesson_content = "\n".join(
        [
            f"# Live B teacher retry lesson: {task_id}",
            "",
            f"- Source run: {run_id}",
            f"- Worker profile: {evidence.get('worker_profile')}",
            f"- Teacher profile: {evidence.get('teacher_profile')}",
            f"- Changed files: {changed_files}",
            f"- Initial verifier failure: {failure}",
            f"- Teacher guidance: {guidance}",
            f"- Verified by: {verifier}",
            "",
            "Prevention rule: when verifier feedback shows an arithmetic or semantic mismatch, apply the teacher guidance exactly, then rerun the verifier before any promotion.",
        ]
    ) + "\n"
    eval_content = "\n".join(
        [
            f"# Regression eval from Live B: {task_id}",
            "",
            f"source_run: {run_id}",
            f"command: {verifier}",
            "expected: first attempt fails, teacher-guided retry passes, dry_run_only remains true, promotion_attempted remains false.",
        ]
    ) + "\n"
    template_content = "\n".join(
        [
            f"# Task template from Live B: {task_id}",
            "",
            "1. Capture verifier failure excerpt.",
            "2. Request concise teacher guidance bound to the failed verifier output.",
            "3. Retry only the scoped changed files.",
            "4. Require verifier pass and source cleanliness before considering promotion readiness.",
        ]
    ) + "\n"
    return build_distillation_proposal(
        proposal_id=proposal_id,
        source_task_id=task_id,
        source_input_id=run_id,
        patches=[
            ProposalPatch(
                asset_type="lesson",
                target_path=f".hermes/lessons/{proposal_id}.md",
                summary="Live B teacher retry lesson from verified real-profile evidence.",
                proposed_content=lesson_content,
                source_ids=source_ids,
            ),
            ProposalPatch(
                asset_type="regression_eval",
                target_path=f".hermes/evals/{proposal_id}.md",
                summary="Regression eval contract for teacher-guided retry evidence.",
                proposed_content=eval_content,
                source_ids=source_ids,
            ),
            ProposalPatch(
                asset_type="task_template",
                target_path=f".hermes/task-templates/{proposal_id}.md",
                summary="Reusable task template for verifier-failure teacher retry loops.",
                proposed_content=template_content,
                source_ids=source_ids,
            ),
        ],
    )
