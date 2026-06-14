from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from feiyue_core.curation.live_asset_loop import (
    CuratorLiveAssetLoopError,
    approve_and_promote_curator_asset,
    live_asset_proposal_from_multi_worker_run,
)
from feiyue_core.workflow.asset_reuse_smoke import AssetReuseSmokeHarness, DEFAULT_COMPARABLE_TASK_ID
from feiyue_core.workflow.capability_feedback import CapabilityFeedbackAggregator
from feiyue_core.workflow.capability_history import CapabilityHistoryCollector
from feiyue_core.workflow.execution import RunCatalog, RunEvidenceLoader, RunEvidenceNotFoundError
from feiyue_core.workflow.longitudinal_gain import LongitudinalGainEvaluator
from feiyue_core.workflow.profile_worker_bridge import _parse_candidate_writes
from feiyue_core.workflow.review_inbox import ReviewInbox
from feiyue_core.workflow.promotion_lifecycle import (
    approve_draft_pr,
    create_approved_draft_pr,
    create_promotion_pr_plan,
    read_draft_pr_approval,
)
from feiyue_core.workflow.release_candidate import (
    approve_production_promotion,
    create_release_candidate_plan,
    read_production_promotion_approval,
    verify_production_promotion_readiness,
)
from feiyue_core.workflow.real_profile_promotion import (
    RealProfilePromotionApproval,
    RealProfilePromotionGate,
    compute_workflow_report_hash,
    read_promotion_approval,
    write_promotion_approval,
)
from feiyue_core.workflow.routing_proposal import (
    RoutingApplyGate,
    RoutingProposalApproval,
    RoutingProposalError,
    RoutingProposalGenerator,
    read_routing_proposal,
    read_routing_proposal_approval,
    recommended_changes_hash,
    write_routing_proposal_approval,
)
from feiyue_core.workflow.real_profile_workflow_runner import RealProfileWorkflowRunReport
from feiyue_core.workflow.live_smoke_plan import build_live_smoke_plan, write_live_smoke_plan
from feiyue_core.workflow.real_multi_worker_live_dry_run import (
    RealMultiWorkerLiveDryRunAuthorization,
    RealMultiWorkerLiveDryRunEvidence,
    RealMultiWorkerLiveDryRunExecutor,
    RealMultiWorkerLiveDryRunStatus,
    RealMultiWorkerTeacherEscalationAuthorization,
)
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlan, MultiWorkerOrchestrationPlanner, MultiWorkerPlanError
from feiyue_core.workflow.multi_worker_workflow_dry_run import (
    MultiWorkerProfileRunnerSelectionError,
    MultiWorkerWorkflowDryRunAuthorization,
    MultiWorkerWorkflowDryRunOrchestrator,
    MultiWorkerWorkflowDryRunReport,
    MultiWorkerWorkflowDryRunStatus,
    build_multi_worker_profile_runner,
    read_multi_worker_dry_run_approval,
    write_multi_worker_dry_run_approval,
)
from feiyue_core.workflow.task_contract import TaskContract


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs",
        description="Inspect persisted Feiyue run evidence and fallback handoff summaries.",
    )
    parser.add_argument("--root", default=".", help="Project root containing .hermes/runs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List persisted run ids")
    list_parser.add_argument("--json", action="store_true", help="Print catalog summary JSON")

    show_parser = subparsers.add_parser("show", help="Print run-evidence.json for a task")
    show_parser.add_argument("task_id")

    handoff_parser = subparsers.add_parser("handoff", help="Render compact fallback handoff summary")
    handoff_parser.add_argument("task_id")

    workflow_smoke_parser = subparsers.add_parser("workflow-smoke", help="Print real profile workflow smoke evidence JSON")
    workflow_smoke_parser.add_argument("run_id")

    workflow_promotion_parser = subparsers.add_parser("workflow-promotion", help="Print real profile workflow promotion evidence JSON")
    workflow_promotion_parser.add_argument("run_id")

    draft_pr_plan_parser = subparsers.add_parser("draft-pr-plan", help="Create a local-only draft PR plan from verified promotion evidence")
    draft_pr_plan_parser.add_argument("run_id")
    draft_pr_plan_parser.add_argument("--allowed-target-branch", action="append", required=True, dest="allowed_target_branches")
    draft_pr_plan_parser.add_argument("--source-branch")

    approve_draft_pr_parser = subparsers.add_parser("approve-draft-pr", help="Create exact approval evidence for draft PR creation")
    approve_draft_pr_parser.add_argument("run_id")
    approve_draft_pr_parser.add_argument("--approved-by", required=True)
    approve_draft_pr_parser.add_argument("--approval-id", required=True)
    approve_draft_pr_parser.add_argument("--reason", required=True)

    create_draft_pr_parser = subparsers.add_parser("create-approved-draft-pr", help="Create a draft PR through the fake adapter using persisted approval")
    create_draft_pr_parser.add_argument("run_id")

    rc_plan_parser = subparsers.add_parser("release-candidate-plan", help="Create a fail-closed local-only release candidate plan")
    rc_plan_parser.add_argument("release_id")
    rc_plan_parser.add_argument("--run-id", required=True)
    rc_plan_parser.add_argument("--allowed-target-branch", action="append", required=True, dest="allowed_target_branches")
    rc_plan_parser.add_argument("--ci-evidence-path", required=True)
    rc_plan_parser.add_argument("--rollback-evidence-path")
    rc_plan_parser.add_argument("--post-promotion-verification-command", action="append", required=True, dest="post_promotion_verification_plan")

    approve_production_parser = subparsers.add_parser("approve-production-promotion", help="Create exact approval evidence for production promotion readiness")
    approve_production_parser.add_argument("release_id")
    approve_production_parser.add_argument("--approved-by", required=True)
    approve_production_parser.add_argument("--approval-id", required=True)
    approve_production_parser.add_argument("--reason", required=True)

    verify_production_parser = subparsers.add_parser("verify-production-promotion-readiness", help="Verify production promotion readiness without mutating production")
    verify_production_parser.add_argument("release_id")

    approve_parser = subparsers.add_parser("approve-promotion", help="Create exact approval evidence for a verified workflow dry run")
    approve_parser.add_argument("run_id")
    approve_parser.add_argument("--target-branch", required=True)
    approve_parser.add_argument("--changed-file", action="append", required=True, dest="changed_files")
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--approval-id", required=True)
    approve_parser.add_argument("--reason", required=True)

    promote_parser = subparsers.add_parser("promote-approved", help="Promote a dry run using persisted approval evidence")
    promote_parser.add_argument("run_id")
    promote_parser.add_argument("--commit-message", required=True)

    feedback_parser = subparsers.add_parser("capability-feedback", help="Summarize workflow evidence into audit-only capability metrics")
    feedback_parser.add_argument("--write-report", action="store_true", help="Persist latest.json and latest.md under .hermes/capability-feedback")

    history_parser = subparsers.add_parser("capability-history", help="Collect workflow evidence into provider-free longitudinal capability history")
    history_parser.add_argument("--write-report", action="store_true", help="Persist history.jsonl, latest.json, and latest.md under .hermes/capability-history")

    longitudinal_parser = subparsers.add_parser("longitudinal-gain", help="Evaluate provider-free before/after gains from capability history")
    longitudinal_parser.add_argument("--history", help="Path to capability-history history.jsonl (defaults to .hermes/capability-history/history.jsonl)")
    longitudinal_parser.add_argument("--min-samples", type=int, default=3, help="Minimum samples required in each before/after window")
    longitudinal_parser.add_argument("--window-size", type=int, default=3, help="Number of earliest/latest samples to use for before/after windows")
    longitudinal_parser.add_argument("--write-report", action="store_true", help="Persist latest.json and latest.md under .hermes/longitudinal-gain")

    asset_reuse_parser = subparsers.add_parser("asset-reuse-smoke", help="Run provider-free lesson asset reuse smoke evidence")
    asset_reuse_parser.add_argument("--run-id", required=True)
    asset_reuse_parser.add_argument("--lesson-path", required=True)
    asset_reuse_parser.add_argument("--comparable-task-id", default=DEFAULT_COMPARABLE_TASK_ID)
    asset_reuse_parser.add_argument("--write-report", action="store_true", help="Persist evidence.json and report.md under .hermes/asset-reuse/<run_id>")

    proposal_parser = subparsers.add_parser("routing-proposal", help="Generate a human-reviewed routing update proposal from capability feedback")
    proposal_parser.add_argument("--proposal-id", required=True)
    proposal_parser.add_argument("--write-proposal", action="store_true", help="Persist proposal.json and proposal.md under .hermes/routing-proposals")

    approve_routing_parser = subparsers.add_parser("approve-routing-proposal", help="Create exact approval evidence for a routing proposal")
    approve_routing_parser.add_argument("--proposal-id", required=True)
    approve_routing_parser.add_argument("--approved-by", required=True)
    approve_routing_parser.add_argument("--approval-id", required=True)
    approve_routing_parser.add_argument("--reason", required=True)

    apply_routing_parser = subparsers.add_parser("apply-approved-routing", help="Apply a routing proposal using persisted exact approval evidence")
    apply_routing_parser.add_argument("--proposal-id", required=True)

    live_smoke_parser = subparsers.add_parser("live-smoke-plan", help="Prepare a fail-closed plan-only live A/B smoke checklist")
    live_smoke_parser.add_argument("--plan-id", required=True)
    live_smoke_parser.add_argument("--run-id", required=True)
    live_smoke_parser.add_argument("--task-id", required=True)
    live_smoke_parser.add_argument("--worker-profile", required=True)
    live_smoke_parser.add_argument("--teacher-profile")
    live_smoke_parser.add_argument("--teacher-escalation-enabled", action="store_true")
    live_smoke_parser.add_argument("--expected-verifier-command", required=True)
    live_smoke_parser.add_argument("--max-profile-calls", type=int, default=1)
    live_smoke_parser.add_argument("--timeout-seconds", type=int, default=120)
    live_smoke_parser.add_argument("--budget-ceiling", default="0.01 USD")
    live_smoke_parser.add_argument("--approval-path")
    live_smoke_parser.add_argument("--teacher-approval-path")
    live_smoke_parser.add_argument("--write-plan", action="store_true", help="Persist plan.json and plan.md under .hermes/live-smoke-plans")

    multi_worker_parser = subparsers.add_parser("multi-worker-plan", help="Create a provider-free multi-worker orchestration plan from approved routing")
    multi_worker_parser.add_argument("--plan-id", required=True)
    multi_worker_parser.add_argument("--task-id", required=True)
    multi_worker_parser.add_argument("--capability", action="append", required=True, dest="capabilities")
    multi_worker_parser.add_argument("--risk-level", choices=["low", "medium", "high"], default="low")
    multi_worker_parser.add_argument("--student-failure-count", type=int, default=0)
    multi_worker_parser.add_argument("--failure-category")
    multi_worker_parser.add_argument("--verifier-confidence", type=float)
    multi_worker_parser.add_argument("--teacher-calls-used", type=int, default=0)
    multi_worker_parser.add_argument("--teacher-call-budget", type=int, default=0)
    multi_worker_parser.add_argument("--write-plan", action="store_true", help="Persist plan.json and plan.md under .hermes/multi-worker-plans")

    multi_worker_workflow_parser = subparsers.add_parser("multi-worker-workflow", help="Print multi-worker workflow dry-run evidence JSON")
    multi_worker_workflow_parser.add_argument("run_id")

    approve_multi_worker_parser = subparsers.add_parser("approve-multi-worker-dry-run", help="Create exact approval evidence for a multi-worker dry-run plan")
    approve_multi_worker_parser.add_argument("--plan-id", required=True)
    approve_multi_worker_parser.add_argument("--approved-by", required=True)
    approve_multi_worker_parser.add_argument("--approval-id", required=True)
    approve_multi_worker_parser.add_argument("--reason", required=True)
    approve_multi_worker_parser.add_argument("--max-profile-calls", type=int, default=1)

    run_multi_worker_parser = subparsers.add_parser("run-approved-multi-worker-dry-run", help="Run an approved multi-worker workflow dry-run with an explicit profile runner")
    run_multi_worker_parser.add_argument("--plan-id", required=True)
    run_multi_worker_parser.add_argument("--run-id", required=True)
    run_multi_worker_parser.add_argument("--source-repo", required=True)
    run_multi_worker_parser.add_argument("--project-name", required=True)
    run_multi_worker_parser.add_argument("--task-id", required=True)
    run_multi_worker_parser.add_argument("--title", required=True)
    run_multi_worker_parser.add_argument("--scope", required=True)
    run_multi_worker_parser.add_argument("--file-to-modify", action="append", required=True, dest="files_to_modify")
    run_multi_worker_parser.add_argument("--verification-command", action="append", required=True, dest="verification_commands")
    run_multi_worker_parser.add_argument("--acceptance-criterion", action="append", default=[], dest="acceptance_criteria")
    run_multi_worker_parser.add_argument("--escalation-rule", default="Approved multi-worker dry-run only.")
    run_multi_worker_parser.add_argument("--profile-runner", choices=["fake", "hermes"], default="fake")
    run_multi_worker_parser.add_argument("--fake-worker-response-json")
    run_multi_worker_parser.add_argument("--hermes-run-record", help="Path to a persisted AuthorizedProviderRunRecord JSON for the selected worker")

    real_multi_worker_parser = subparsers.add_parser(
        "real-multi-worker-live-dry-run",
        help="Run an explicitly authorized real multi-worker live dry-run seam and persist history evidence",
    )
    real_multi_worker_parser.add_argument("--plan-id", required=True)
    real_multi_worker_parser.add_argument("--run-id", required=True)
    real_multi_worker_parser.add_argument("--source-repo", required=True)
    real_multi_worker_parser.add_argument("--project-name", required=True)
    real_multi_worker_parser.add_argument("--task-id", required=True)
    real_multi_worker_parser.add_argument("--title", required=True)
    real_multi_worker_parser.add_argument("--scope", required=True)
    real_multi_worker_parser.add_argument("--file-to-modify", action="append", required=True, dest="files_to_modify")
    real_multi_worker_parser.add_argument("--verification-command", action="append", required=True, dest="verification_commands")
    real_multi_worker_parser.add_argument("--acceptance-criterion", action="append", default=[], dest="acceptance_criteria")
    real_multi_worker_parser.add_argument("--escalation-rule", default="Approved real multi-worker live dry-run only.")
    real_multi_worker_parser.add_argument("--authorization-path", required=True)
    real_multi_worker_parser.add_argument("--teacher-authorization-path")
    real_multi_worker_parser.add_argument("--profile-runner", choices=["fake", "hermes"], default="fake")
    real_multi_worker_parser.add_argument("--fake-worker-response-json")
    real_multi_worker_parser.add_argument("--hermes-run-record", help="Path to a persisted AuthorizedProviderRunRecord JSON for the selected worker")
    real_multi_worker_parser.add_argument("--cost-usd", type=float, default=0.0)
    real_multi_worker_parser.add_argument("--latency-ms", type=float, default=0.0)

    review_inbox_parser = subparsers.add_parser("review-inbox", help="List pending local approval/review items without mutating state")
    review_inbox_parser.add_argument("--format", choices=["json"], default="json")

    curator_live_parser = subparsers.add_parser("curator-live-proposal", help="Build a review-required asset proposal from verified Live B evidence")
    curator_live_parser.add_argument("--run-id", required=True)
    curator_live_parser.add_argument("--proposal-id", required=True)
    curator_live_parser.add_argument("--write-proposal", action="store_true")

    promote_curator_parser = subparsers.add_parser(
        "promote-curator-asset",
        help="Approve and promote one project-local curator asset proposal patch selected by --patch-id or --patch-index",
    )
    promote_curator_parser.add_argument("--proposal-id", required=True)
    promote_curator_parser.add_argument("--reviewer", required=True)
    promote_curator_parser.add_argument("--reason", required=True)
    promote_curator_parser.add_argument("--rollback-ref", required=True)
    promote_curator_parser.add_argument("--patch-id")
    promote_curator_parser.add_argument("--patch-index", type=int, default=0)

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.root)
    loader = RunEvidenceLoader(root)

    try:
        if args.command == "curator-live-proposal":
            proposal = live_asset_proposal_from_multi_worker_run(
                project_root=root,
                run_id=args.run_id,
                proposal_id=args.proposal_id,
                write_proposal=args.write_proposal,
            )
            print(proposal.model_dump_json(indent=2))
            return 0
        if args.command == "promote-curator-asset":
            evidence = approve_and_promote_curator_asset(
                project_root=root,
                proposal_id=args.proposal_id,
                reviewer=args.reviewer,
                reason=args.reason,
                rollback_ref=args.rollback_ref,
                patch_id=args.patch_id,
                patch_index=args.patch_index,
            )
            print(evidence.model_dump_json(indent=2))
            return 0
        if args.command == "review-inbox":
            summary = ReviewInbox(root).summary()
            print(summary.model_dump_json(indent=2))
            return 0
        if args.command == "list":
            catalog = RunCatalog(root)
            if args.json:
                print(catalog.summary().model_dump_json(indent=2))
                return 0
            for run in catalog.summary().runs:
                print(run.task_id)
            return 0
        if args.command == "show":
            evidence = loader.load(args.task_id)
            print(evidence.model_dump_json(indent=2))
            return 0
        if args.command == "handoff":
            print(loader.render_handoff_summary(args.task_id), end="")
            return 0
        if args.command == "workflow-smoke":
            evidence_path = root / ".hermes" / "workflow-smokes" / args.run_id / "evidence.json"
            if not evidence_path.exists():
                print(f"Workflow smoke evidence not found for run_id: {args.run_id}", file=sys.stderr)
                return 2
            print(json.dumps(json.loads(evidence_path.read_text(encoding="utf-8")), indent=2, sort_keys=True))
            return 0
        if args.command == "workflow-promotion":
            evidence_path = root / ".hermes" / "workflow-promotions" / args.run_id / "promotion-evidence.json"
            if not evidence_path.exists():
                print(f"Workflow promotion evidence not found for run_id: {args.run_id}", file=sys.stderr)
                return 2
            print(json.dumps(json.loads(evidence_path.read_text(encoding="utf-8")), indent=2, sort_keys=True))
            return 0
        if args.command == "draft-pr-plan":
            plan = create_promotion_pr_plan(
                project_root=root,
                run_id=args.run_id,
                allowed_target_branches=args.allowed_target_branches,
                source_branch=args.source_branch,
            )
            print(plan.model_dump_json(indent=2))
            return 0
        if args.command == "approve-draft-pr":
            approval = approve_draft_pr(
                project_root=root,
                run_id=args.run_id,
                approved_by=args.approved_by,
                approval_id=args.approval_id,
                reason=args.reason,
            )
            print(approval.model_dump_json(indent=2))
            return 0
        if args.command == "create-approved-draft-pr":
            approval = read_draft_pr_approval(root, args.run_id)
            evidence = create_approved_draft_pr(project_root=root, run_id=args.run_id, approval=approval)
            print(evidence.model_dump_json(indent=2))
            return 0
        if args.command == "release-candidate-plan":
            plan = create_release_candidate_plan(
                project_root=root,
                release_id=args.release_id,
                run_id=args.run_id,
                allowed_target_branches=args.allowed_target_branches,
                ci_evidence_path=args.ci_evidence_path,
                rollback_evidence_path=args.rollback_evidence_path,
                post_promotion_verification_plan=args.post_promotion_verification_plan,
            )
            print(plan.model_dump_json(indent=2))
            return 0
        if args.command == "approve-production-promotion":
            approval = approve_production_promotion(
                project_root=root,
                release_id=args.release_id,
                approved_by=args.approved_by,
                approval_id=args.approval_id,
                reason=args.reason,
            )
            print(approval.model_dump_json(indent=2))
            return 0
        if args.command == "verify-production-promotion-readiness":
            approval = read_production_promotion_approval(root, args.release_id)
            readiness = verify_production_promotion_readiness(project_root=root, release_id=args.release_id, approval=approval)
            print(readiness.model_dump_json(indent=2))
            return 0
        if args.command == "approve-promotion":
            dry_run = _load_workflow_smoke_report(root, args.run_id)
            if dry_run.workflow_report is None:
                print(f"Workflow smoke report is missing workflow_report for run_id: {args.run_id}", file=sys.stderr)
                return 2
            approval = RealProfilePromotionApproval(
                approval_id=args.approval_id,
                approved_by=args.approved_by,
                run_id=dry_run.run_id,
                task_id=dry_run.task_id,
                approved_action="promote_verified_dry_run",
                changed_files=args.changed_files,
                target_branch=args.target_branch,
                source_commit_sha=_git("rev-parse", "HEAD", cwd=root).strip(),
                workflow_report_hash=compute_workflow_report_hash(dry_run.workflow_report),
                approved_at=datetime.now(UTC).isoformat(),
                reason=args.reason,
            )
            write_promotion_approval(approval, root)
            print(approval.model_dump_json(indent=2))
            return 0
        if args.command == "promote-approved":
            dry_run = _load_workflow_smoke_report(root, args.run_id)
            approval = read_promotion_approval(root, args.run_id)
            candidate_writes = _extract_latest_candidate_writes(dry_run)
            result = RealProfilePromotionGate().promote_verified_dry_run(
                source_repo=root,
                dry_run_report=dry_run,
                candidate_writes=candidate_writes,
                target_branch=approval.target_branch,
                commit_message=args.commit_message,
                approval=approval,
                evidence_root=root,
            )
            print(result.model_dump_json(indent=2))
            return 0
        if args.command == "capability-feedback":
            aggregator = CapabilityFeedbackAggregator(root)
            report = aggregator.write_report() if args.write_report else aggregator.build_report()
            print(report.model_dump_json(indent=2))
            return 0
        if args.command == "capability-history":
            collector = CapabilityHistoryCollector(root)
            report = collector.write_report() if args.write_report else collector.build_report()
            print(report.model_dump_json(indent=2))
            return 0
        if args.command == "longitudinal-gain":
            history_path = Path(args.history) if args.history else root / ".hermes" / "capability-history" / "history.jsonl"
            evaluator = LongitudinalGainEvaluator.from_history_path(
                history_path,
                min_samples=args.min_samples,
                window_size=args.window_size,
            )
            report = evaluator.write_report(root) if args.write_report else evaluator.build_report()
            print(report.model_dump_json(indent=2))
            return 0
        if args.command == "asset-reuse-smoke":
            report = AssetReuseSmokeHarness(root).run(
                run_id=args.run_id,
                lesson_path=args.lesson_path,
                comparable_task_id=args.comparable_task_id,
                write_report=args.write_report,
            )
            print(report.model_dump_json(indent=2))
            return 0
        if args.command == "routing-proposal":
            generator = RoutingProposalGenerator(root)
            proposal = generator.write_proposal(proposal_id=args.proposal_id) if args.write_proposal else generator.build_proposal(proposal_id=args.proposal_id)
            print(proposal.model_dump_json(indent=2))
            return 0
        if args.command == "approve-routing-proposal":
            proposal = read_routing_proposal(root, args.proposal_id)
            approval = RoutingProposalApproval(
                approval_id=args.approval_id,
                approved_by=args.approved_by,
                proposal_id=proposal.proposal_id,
                approved_action="apply_reviewed_routing_proposal",
                source_feedback_hash=proposal.source_feedback_hash,
                current_routing_hash=proposal.current_routing_hash,
                recommended_changes_hash=recommended_changes_hash(proposal.recommended_changes),
                approved_at=datetime.now(UTC).isoformat(),
                reason=args.reason,
            )
            write_routing_proposal_approval(approval, root)
            print(approval.model_dump_json(indent=2))
            return 0
        if args.command == "apply-approved-routing":
            proposal = read_routing_proposal(root, args.proposal_id)
            approval = read_routing_proposal_approval(root, args.proposal_id)
            result = RoutingApplyGate(root).apply_proposal(proposal=proposal, approval=approval)
            print(result.model_dump_json(indent=2))
            return 0
        if args.command == "live-smoke-plan":
            kwargs = {
                "project_root": root,
                "plan_id": args.plan_id,
                "run_id": args.run_id,
                "task_id": args.task_id,
                "worker_profile_id": args.worker_profile,
                "teacher_profile_id": args.teacher_profile,
                "teacher_escalation_enabled": args.teacher_escalation_enabled,
                "expected_verifier_command": args.expected_verifier_command,
                "max_profile_calls": args.max_profile_calls,
                "timeout_seconds": args.timeout_seconds,
                "budget_ceiling": args.budget_ceiling,
                "approval_path": args.approval_path,
                "teacher_approval_path": args.teacher_approval_path,
            }
            plan = write_live_smoke_plan(**kwargs) if args.write_plan else build_live_smoke_plan(**kwargs)
            print(plan.model_dump_json(indent=2))
            return 0
        if args.command == "multi-worker-plan":
            planner = MultiWorkerOrchestrationPlanner(root)
            kwargs = {
                "plan_id": args.plan_id,
                "task_id": args.task_id,
                "required_capabilities": args.capabilities,
                "risk_level": args.risk_level,
                "student_failure_count": args.student_failure_count,
                "failure_category": args.failure_category,
                "verifier_confidence": args.verifier_confidence,
                "teacher_calls_used": args.teacher_calls_used,
                "teacher_call_budget": args.teacher_call_budget,
            }
            plan = planner.write_plan(**kwargs) if args.write_plan else planner.plan(**kwargs)
            print(plan.model_dump_json(indent=2))
            return 0
        if args.command == "multi-worker-workflow":
            evidence_path = root / ".hermes" / "multi-worker-workflows" / args.run_id / "evidence.json"
            if not evidence_path.exists():
                print(f"Multi-worker workflow evidence not found for run_id: {args.run_id}", file=sys.stderr)
                return 2
            print(json.dumps(json.loads(evidence_path.read_text(encoding="utf-8")), indent=2, sort_keys=True))
            return 0
        if args.command == "approve-multi-worker-dry-run":
            plan = _read_multi_worker_plan(root, args.plan_id)
            approval = MultiWorkerWorkflowDryRunAuthorization(
                authorization_id=args.approval_id,
                authorized_by=args.approved_by,
                plan_id=plan.plan_id,
                task_id=plan.task_id,
                approved_action="execute_multi_worker_workflow_dry_run",
                worker_profile_ids=plan.route.worker_profile_ids,
                scopes=["multi_worker_workflow_execute"],
                max_profile_calls=args.max_profile_calls,
                dry_run_only=True,
                approved_at=datetime.now(UTC).isoformat(),
                reason=args.reason,
            )
            write_multi_worker_dry_run_approval(approval, root)
            print(approval.model_dump_json(indent=2))
            return 0
        if args.command == "run-approved-multi-worker-dry-run":
            plan = _read_multi_worker_plan(root, args.plan_id)
            approval = read_multi_worker_dry_run_approval(root, args.plan_id)
            worker_profile = plan.route.worker_profile_ids[0]
            contract = TaskContract(
                task_id=args.task_id,
                title=args.title,
                scope=args.scope,
                files_to_modify=args.files_to_modify,
                acceptance_criteria=args.acceptance_criteria,
                verification_commands=args.verification_commands,
                escalation_rule=args.escalation_rule,
            )
            try:
                runner = build_multi_worker_profile_runner(
                    mode=args.profile_runner,
                    project_root=root,
                    worker_profile=worker_profile,
                    fake_worker_response_json=args.fake_worker_response_json,
                    hermes_run_record_path=args.hermes_run_record,
                )
            except MultiWorkerProfileRunnerSelectionError as exc:
                result = _profile_runner_selection_blocked_report(
                    root=root,
                    run_id=args.run_id,
                    contract=contract,
                    plan=plan,
                    reason=str(exc),
                )
                print(result.model_dump_json(indent=2))
                return 2
            result = MultiWorkerWorkflowDryRunOrchestrator(profile_runner=runner).run(
                project_root=root,
                source_repo=Path(args.source_repo),
                contract=contract,
                project_name=args.project_name,
                plan=plan,
                authorization=approval,
                run_id=args.run_id,
            )
            print(result.model_dump_json(indent=2))
            return 0
        if args.command == "real-multi-worker-live-dry-run":
            plan = _read_multi_worker_plan(root, args.plan_id)
            worker_profile = plan.route.worker_profile_ids[0]
            contract = TaskContract(
                task_id=args.task_id,
                title=args.title,
                scope=args.scope,
                files_to_modify=args.files_to_modify,
                acceptance_criteria=args.acceptance_criteria,
                verification_commands=args.verification_commands,
                escalation_rule=args.escalation_rule,
            )
            authorization = _read_real_multi_worker_authorization(Path(args.authorization_path))
            teacher_authorization = (
                _read_real_multi_worker_teacher_authorization(Path(args.teacher_authorization_path))
                if args.teacher_authorization_path
                else None
            )
            try:
                runner = build_multi_worker_profile_runner(
                    mode=args.profile_runner,
                    project_root=root,
                    worker_profile=worker_profile,
                    fake_worker_response_json=args.fake_worker_response_json,
                    hermes_run_record_path=args.hermes_run_record,
                )
            except MultiWorkerProfileRunnerSelectionError as exc:
                result = _real_multi_worker_selection_blocked_evidence(
                    root=root,
                    run_id=args.run_id,
                    source_repo=Path(args.source_repo),
                    contract=contract,
                    plan=plan,
                    authorization=authorization,
                    teacher_authorization=teacher_authorization,
                    reason=str(exc),
                    cost_usd=args.cost_usd,
                    latency_ms=args.latency_ms,
                )
                print(result.model_dump_json(indent=2))
                return 2
            result = RealMultiWorkerLiveDryRunExecutor(profile_runner=runner).run(
                project_root=root,
                source_repo=Path(args.source_repo),
                contract=contract,
                project_name=args.project_name,
                plan=plan,
                authorization=authorization,
                run_id=args.run_id,
                teacher_escalation_authorization=teacher_authorization,
                cost_usd=args.cost_usd,
                latency_ms=args.latency_ms,
            )
            print(result.model_dump_json(indent=2))
            return 0 if result.status != "blocked" else 2
    except (RunEvidenceNotFoundError, RoutingProposalError, MultiWorkerPlanError, CuratorLiveAssetLoopError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


def _load_workflow_smoke_report(root: Path, run_id: str) -> RealProfileWorkflowRunReport:
    evidence_path = root / ".hermes" / "workflow-smokes" / run_id / "evidence.json"
    if not evidence_path.exists():
        raise FileNotFoundError(f"Workflow smoke evidence not found for run_id: {run_id}")
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload.pop("written_at", None)
    return RealProfileWorkflowRunReport.model_validate(payload)


def _read_multi_worker_plan(root: Path, plan_id: str) -> MultiWorkerOrchestrationPlan:
    plan_path = root / ".hermes" / "multi-worker-plans" / plan_id / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Multi-worker plan evidence not found for plan_id: {plan_id}")
    return MultiWorkerOrchestrationPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))


def _read_real_multi_worker_authorization(path: Path) -> RealMultiWorkerLiveDryRunAuthorization:
    if not path.exists():
        raise FileNotFoundError(f"Real multi-worker live dry-run authorization not found: {path}")
    return RealMultiWorkerLiveDryRunAuthorization.model_validate_json(path.read_text(encoding="utf-8"))


def _read_real_multi_worker_teacher_authorization(path: Path) -> RealMultiWorkerTeacherEscalationAuthorization:
    if not path.exists():
        raise FileNotFoundError(f"Real multi-worker teacher escalation authorization not found: {path}")
    return RealMultiWorkerTeacherEscalationAuthorization.model_validate_json(path.read_text(encoding="utf-8"))


def _real_multi_worker_selection_blocked_evidence(
    *,
    root: Path,
    run_id: str,
    source_repo: Path,
    contract: TaskContract,
    plan: MultiWorkerOrchestrationPlan,
    authorization: RealMultiWorkerLiveDryRunAuthorization,
    teacher_authorization: RealMultiWorkerTeacherEscalationAuthorization | None,
    reason: str,
    cost_usd: float,
    latency_ms: float,
) -> RealMultiWorkerLiveDryRunEvidence:
    source_clean = _source_repo_clean(source_repo)
    now = datetime.now(UTC).isoformat()
    evidence = RealMultiWorkerLiveDryRunEvidence(
        run_id=run_id,
        task_id=contract.task_id,
        plan_id=plan.plan_id,
        status=RealMultiWorkerLiveDryRunStatus.BLOCKED,
        verified=False,
        worker_profile=plan.route.worker_profile_ids[0] if plan.route.worker_profile_ids else None,
        teacher_profile=plan.route.teacher_profile_id,
        provider_call_count=0,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        source_clean=source_clean,
        source_repo_clean=source_clean,
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        route_plan_status=str(plan.route.status),
        routing_apply_evidence_id=plan.routing_apply_evidence_id,
        authorization_id=authorization.authorization_id,
        teacher_authorization_id=teacher_authorization.authorization_id if teacher_authorization is not None else None,
        reason_codes=["profile_runner_selection_failed", reason],
        started_at=now,
        completed_at=now,
    )
    RealMultiWorkerLiveDryRunExecutor._write_evidence(evidence, root)
    return evidence


def _source_repo_clean(source_repo: Path) -> bool:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=source_repo, text=True, capture_output=True, check=False)
    return completed.returncode == 0 and completed.stdout == ""


def _profile_runner_selection_blocked_report(
    *,
    root: Path,
    run_id: str,
    contract: TaskContract,
    plan: MultiWorkerOrchestrationPlan,
    reason: str,
) -> MultiWorkerWorkflowDryRunReport:
    report = MultiWorkerWorkflowDryRunReport(
        run_id=run_id,
        task_id=contract.task_id,
        plan_id=plan.plan_id,
        status=MultiWorkerWorkflowDryRunStatus.BLOCKED,
        worker_profile=plan.route.worker_profile_ids[0] if plan.route.worker_profile_ids else None,
        teacher_profile=plan.route.teacher_profile_id,
        provider_call_count=0,
        reason_codes=["profile_runner_selection_failed", reason],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        route_plan_status=str(plan.route.status),
        routing_apply_evidence_id=plan.routing_apply_evidence_id,
    )
    MultiWorkerWorkflowDryRunOrchestrator._write_evidence(report, root)
    return report


def _extract_latest_candidate_writes(report: RealProfileWorkflowRunReport):
    for stdout in reversed(report.stdout_redacted):
        try:
            return _parse_candidate_writes(stdout)
        except ValueError:
            continue
    raise ValueError(f"No parseable candidate writes found for run_id: {report.run_id}")


def _git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


if __name__ == "__main__":
    raise SystemExit(main())
