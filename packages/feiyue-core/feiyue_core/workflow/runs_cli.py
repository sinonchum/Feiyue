from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from feiyue_core.workflow.capability_feedback import CapabilityFeedbackAggregator
from feiyue_core.workflow.execution import RunCatalog, RunEvidenceLoader, RunEvidenceNotFoundError
from feiyue_core.workflow.profile_worker_bridge import _parse_candidate_writes
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
from feiyue_core.workflow.multi_worker_orchestration import MultiWorkerOrchestrationPlan, MultiWorkerOrchestrationPlanner, MultiWorkerPlanError
from feiyue_core.workflow.multi_worker_workflow_dry_run import (
    MultiWorkerWorkflowDryRunAuthorization,
    MultiWorkerWorkflowDryRunOrchestrator,
    read_multi_worker_dry_run_approval,
    write_multi_worker_dry_run_approval,
)
from feiyue_core.providers.profile_runner import FakeProfileRunner
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

    run_multi_worker_parser = subparsers.add_parser("run-approved-multi-worker-dry-run", help="Run an approved multi-worker workflow dry-run with an explicit fake profile response")
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
    run_multi_worker_parser.add_argument("--fake-worker-response-json", required=True)

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.root)
    loader = RunEvidenceLoader(root)

    try:
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
            runner = FakeProfileRunner({worker_profile: args.fake_worker_response_json})
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
    except (RunEvidenceNotFoundError, RoutingProposalError, MultiWorkerPlanError, FileNotFoundError) as exc:
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
