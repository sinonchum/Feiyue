from __future__ import annotations

import shlex
import subprocess
import tempfile
from enum import StrEnum
from pathlib import Path
from collections import Counter

from pydantic import Field

from feiyue_core.safety import (
    GovernanceAction,
    HumanApprovalRecord,
    PolicyDecision,
    PolicyGovernor,
    PolicyRequest,
    RiskLevel,
)
from feiyue_core.sandbox import WorktreeSandbox
from feiyue_core.sandbox.command_runner import CommandRunner, CommandResult, CommandStatus
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.bug_dossier import BugDossier
from feiyue_core.workflow.lesson_packet import LessonPacket
from feiyue_core.workflow.regression_eval import (
    RegressionCheck,
    UnsafeRegressionCommandError,
    build_regression_check_from_lesson,
)
from feiyue_core.workflow.task_contract import TaskContract


class WorkflowExecutionStatus(StrEnum):
    VERIFIED = "verified"
    NEEDS_TEACHER = "needs_teacher"
    BLOCKED = "blocked"


class PromotionStatus(StrEnum):
    PROMOTED = "promoted"
    BLOCKED = "blocked"
    FAILED = "failed"


class CandidateFileWrite(FeiyueModel):
    """A provider-free candidate side effect for the M11 toy workflow path."""

    path: str
    content: str

class ProductionPromotionRequest(FeiyueModel):
    """Explicit authorization boundary for production promotion side effects."""

    task_id: str
    target_branch: str
    allowed_target_branches: list[str] = Field(default_factory=list)
    rollback_plan: str
    approval_record: HumanApprovalRecord | None = None

    @property
    def required_approval_action(self) -> str:
        return f"production_promotion:{self.target_branch}"

class PromotionSafetyReport(FeiyueModel):
    """Pre/post safety evidence for a production promotion attempt."""

    authorized: bool
    reasons: list[str] = Field(default_factory=list)
    requested_target_branch: str
    actual_target_branch: str
    approval_applies: bool = False
    rollback_plan_recorded: bool = False
    rollback_plan: str | None = None
    rollback_ref: str | None = None
    source_repo_clean_before: bool | None = None
    source_repo_clean_after: bool | None = None
    promoted_ref: str | None = None
    target_ref_verified: bool = False
    promotion_worktree_removed: bool = True

class TeacherGuidanceEvent(FeiyueModel):
    """Auditable fake-teacher guidance used between worker attempts."""

    request_id: str
    attempt_index: int = 2
    trigger: str
    guidance: str
    source_bug_dossier_task_id: str


class AttemptEvidence(FeiyueModel):
    """Verifier-gated evidence for one provider-free worker attempt."""

    attempt_index: int
    changed_files: list[str] = Field(default_factory=list)
    verification_command: str | None = None
    verification_passed: bool
    failure_reason: str | None = None
    teacher_request_id: str | None = None


class PromotionResult(FeiyueModel):
    """Result of promoting a verified workflow patch into a target branch."""

    status: PromotionStatus
    target_branch: str
    commit_sha: str | None = None
    promoted_files: list[str] = Field(default_factory=list)
    reason: str | None = None
    source_repo_clean: bool
    promotion_worktree_removed: bool
    policy_decision: PolicyDecision | None = None
    side_effect_performed: bool = False
    rollback_plan: str | None = None
    rollback_ref: str | None = None
    safety_report: PromotionSafetyReport | None = None


class WorkflowExecutionReport(FeiyueModel):
    """Deterministic M11 worker execution report."""

    task_id: str
    status: WorkflowExecutionStatus
    changed_files: list[str] = Field(default_factory=list)
    verification_passed: bool
    promotion_ready: bool
    source_repo_clean: bool
    sandbox_removed: bool
    verification_command: str | None = None
    bug_dossier: BugDossier | None = None
    lesson_candidate: LessonPacket | None = None
    regression_check: RegressionCheck | None = None
    attempt_count: int = 1
    teacher_guidance_events: list[TeacherGuidanceEvent] = Field(default_factory=list)
    attempt_evidence: list[AttemptEvidence] = Field(default_factory=list)
    policy_decision: PolicyDecision | None = None
    execution_performed: bool = True
    retry_performed: bool = False


class RunEvidenceIndex(FeiyueModel):
    """Machine-readable handoff index for fallback models and dashboards."""

    task_id: str
    status: str
    policy_action: str | None = None
    policy_reason: str | None = None
    execution_performed: bool
    retry_performed: bool
    promotion_status: str | None = None
    promotion_side_effect_performed: bool | None = None
    approval_exists: bool = False
    approval_id: str | None = None
    approval_approver: str | None = None
    approval_action: str | None = None
    approval_applies: bool = False
    safe_to_retry: bool
    next_safe_action: str
    report_paths: dict[str, str] = Field(default_factory=dict)


class RunCatalogItem(FeiyueModel):
    """Compact run row for dashboards, APIs, and CLI listing."""

    task_id: str
    status: str
    policy_action: str | None = None
    policy_reason: str | None = None
    safe_to_retry: bool
    next_safe_action: str
    approval_exists: bool
    approval_applies: bool


class RunCatalogSummary(FeiyueModel):
    """Aggregate view over persisted run evidence."""

    total_runs: int
    safe_to_retry_count: int
    next_action_counts: dict[str, int] = Field(default_factory=dict)
    runs: list[RunCatalogItem] = Field(default_factory=list)


class RunEvidenceNotFoundError(FileNotFoundError):
    """Raised when a persisted run evidence index is missing."""

    def __init__(self, *, task_id: str, path: Path) -> None:
        self.task_id = task_id
        self.path = path
        super().__init__(f"Run evidence index not found for task {task_id}: {path}")


class WorkflowReportArtifacts(FeiyueModel):
    """File paths created by WorkflowReportWriter."""

    run_dir: Path
    execution_json_path: Path
    execution_markdown_path: Path
    run_evidence_json_path: Path
    approval_json_path: Path | None = None
    bug_dossier_markdown_path: Path | None = None
    teacher_guidance_markdown_path: Path | None = None
    promotion_json_path: Path | None = None
    promotion_markdown_path: Path | None = None


class RunEvidenceLoader:
    """Load persisted run evidence and render compact fallback handoff summaries."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def load(self, task_id: str) -> RunEvidenceIndex:
        path = self._evidence_path(task_id)
        if not path.exists():
            raise RunEvidenceNotFoundError(task_id=task_id, path=path)
        return RunEvidenceIndex.model_validate_json(path.read_text(encoding="utf-8"))

    def load_approval(self, task_id: str) -> HumanApprovalRecord | None:
        evidence = self.load(task_id)
        approval_path = evidence.report_paths.get("approval")
        if not approval_path:
            return None
        path = self.project_root / ".hermes" / "runs" / task_id / approval_path
        if not path.exists():
            return None
        return HumanApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def render_handoff_summary(self, task_id: str) -> str:
        evidence = self.load(task_id)
        lines = [
            "# Fallback Handoff Summary",
            "",
            f"- task_id: {evidence.task_id}",
            f"- status: {evidence.status}",
            f"- policy_action: {evidence.policy_action or 'None'}",
            f"- policy_reason: {evidence.policy_reason or 'None'}",
            f"- execution_performed: {evidence.execution_performed}",
            f"- retry_performed: {evidence.retry_performed}",
            f"- promotion_status: {evidence.promotion_status or 'None'}",
            f"- promotion_side_effect_performed: {evidence.promotion_side_effect_performed}",
            f"- safe_to_retry: {evidence.safe_to_retry}",
            f"- next_safe_action: {evidence.next_safe_action}",
            "",
            "## Approval Evidence",
            f"- approval_exists: {evidence.approval_exists}",
            f"- approval_id: {evidence.approval_id or 'None'}",
            f"- approval_approver: {evidence.approval_approver or 'None'}",
            f"- approval_action: {evidence.approval_action or 'None'}",
            f"- approval_applies: {evidence.approval_applies}",
            "",
            "## Report Paths",
        ]
        for key in sorted(evidence.report_paths):
            lines.append(f"- {key}: {evidence.report_paths[key]}")
        return "\n".join(lines) + "\n"

    def _evidence_path(self, task_id: str) -> Path:
        return self.project_root / ".hermes" / "runs" / task_id / "run-evidence.json"


class RunCatalog:
    """Provider-free catalog over persisted run evidence for M11 productization."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.loader = RunEvidenceLoader(project_root)

    def summary(self) -> RunCatalogSummary:
        evidence_items = [self.loader.load(task_id) for task_id in self._list_run_ids()]
        runs = [
            RunCatalogItem(
                task_id=evidence.task_id,
                status=evidence.status,
                policy_action=evidence.policy_action,
                policy_reason=evidence.policy_reason,
                safe_to_retry=evidence.safe_to_retry,
                next_safe_action=evidence.next_safe_action,
                approval_exists=evidence.approval_exists,
                approval_applies=evidence.approval_applies,
            )
            for evidence in evidence_items
        ]
        next_action_counts = Counter(run.next_safe_action for run in runs)
        return RunCatalogSummary(
            total_runs=len(runs),
            safe_to_retry_count=sum(1 for run in runs if run.safe_to_retry),
            next_action_counts=dict(sorted(next_action_counts.items())),
            runs=runs,
        )

    def _list_run_ids(self) -> list[str]:
        runs_dir = self.project_root / ".hermes" / "runs"
        if not runs_dir.exists():
            return []
        return sorted(
            path.name
            for path in runs_dir.iterdir()
            if path.is_dir() and (path / "run-evidence.json").exists()
        )


class WorkflowReportWriter:
    """Persist M11 workflow reports under .hermes/runs/<task_id>."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def write(
        self,
        *,
        report: WorkflowExecutionReport,
        promotion: PromotionResult | None = None,
        approval: HumanApprovalRecord | None = None,
    ) -> WorkflowReportArtifacts:
        run_dir = self.project_root / ".hermes" / "runs" / report.task_id
        run_dir.mkdir(parents=True, exist_ok=True)

        execution_json_path = run_dir / "execution-report.json"
        execution_markdown_path = run_dir / "execution-report.md"
        execution_json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        execution_markdown_path.write_text(_render_execution_report_markdown(report), encoding="utf-8")

        bug_path: Path | None = None
        if report.bug_dossier is not None:
            bug_path = run_dir / "bug-dossier.md"
            bug_path.write_text(report.bug_dossier.render_markdown(), encoding="utf-8")

        teacher_path: Path | None = None
        if report.teacher_guidance_events:
            teacher_path = run_dir / "teacher-guidance.md"
            teacher_path.write_text(_render_teacher_guidance_markdown(report), encoding="utf-8")

        promotion_json_path: Path | None = None
        promotion_markdown_path: Path | None = None
        if promotion is not None:
            promotion_json_path = run_dir / "promotion-result.json"
            promotion_markdown_path = run_dir / "promotion-result.md"
            promotion_json_path.write_text(promotion.model_dump_json(indent=2), encoding="utf-8")
            promotion_markdown_path.write_text(_render_promotion_markdown(promotion), encoding="utf-8")

        approval_json_path: Path | None = None
        if approval is not None:
            approval_json_path = run_dir / "approval.json"
            approval_json_path.write_text(approval.model_dump_json(indent=2), encoding="utf-8")

        run_evidence_json_path = run_dir / "run-evidence.json"
        run_evidence = _build_run_evidence_index(
            report=report,
            promotion=promotion,
            approval=approval,
            approval_json_path=approval_json_path,
            bug_dossier_markdown_path=bug_path,
            teacher_guidance_markdown_path=teacher_path,
            promotion_markdown_path=promotion_markdown_path,
        )
        run_evidence_json_path.write_text(run_evidence.model_dump_json(indent=2), encoding="utf-8")

        return WorkflowReportArtifacts(
            run_dir=run_dir,
            execution_json_path=execution_json_path,
            execution_markdown_path=execution_markdown_path,
            run_evidence_json_path=run_evidence_json_path,
            approval_json_path=approval_json_path,
            bug_dossier_markdown_path=bug_path,
            teacher_guidance_markdown_path=teacher_path,
            promotion_json_path=promotion_json_path,
            promotion_markdown_path=promotion_markdown_path,
        )


def _build_run_evidence_index(
    *,
    report: WorkflowExecutionReport,
    promotion: PromotionResult | None,
    approval: HumanApprovalRecord | None,
    approval_json_path: Path | None,
    bug_dossier_markdown_path: Path | None,
    teacher_guidance_markdown_path: Path | None,
    promotion_markdown_path: Path | None,
) -> RunEvidenceIndex:
    policy_decision = promotion.policy_decision if promotion and promotion.policy_decision else report.policy_decision
    approval_applies = _approval_applies_to_policy_decision(
        approval=approval,
        task_id=report.task_id,
        policy_decision=policy_decision,
    )
    report_paths = {"execution_report": "execution-report.md", "execution_json": "execution-report.json"}
    if bug_dossier_markdown_path is not None:
        report_paths["bug_dossier"] = bug_dossier_markdown_path.name
    if teacher_guidance_markdown_path is not None:
        report_paths["teacher_guidance"] = teacher_guidance_markdown_path.name
    if promotion_markdown_path is not None:
        report_paths["promotion_result"] = promotion_markdown_path.name
    if approval_json_path is not None:
        report_paths["approval"] = approval_json_path.name

    return RunEvidenceIndex(
        task_id=report.task_id,
        status=report.status.value,
        policy_action=policy_decision.action.value if policy_decision is not None else None,
        policy_reason=policy_decision.reason.value if policy_decision is not None else None,
        execution_performed=report.execution_performed,
        retry_performed=report.retry_performed,
        promotion_status=promotion.status.value if promotion is not None else None,
        promotion_side_effect_performed=promotion.side_effect_performed if promotion is not None else None,
        approval_exists=approval is not None,
        approval_id=approval.approval_id if approval is not None else None,
        approval_approver=approval.approver if approval is not None else None,
        approval_action=approval.approved_action if approval is not None else None,
        approval_applies=approval_applies,
        safe_to_retry=_compute_safe_to_retry(report=report, promotion=promotion),
        next_safe_action=_compute_next_safe_action(report=report, promotion=promotion, policy_decision=policy_decision),
        report_paths=report_paths,
    )


def _approval_applies_to_policy_decision(
    *,
    approval: HumanApprovalRecord | None,
    task_id: str,
    policy_decision: PolicyDecision | None,
) -> bool:
    if approval is None or policy_decision is None:
        return False
    operation = policy_decision.audit_metadata.get("operation")
    return approval.task_id == task_id and approval.approved_action == operation


def _compute_safe_to_retry(*, report: WorkflowExecutionReport, promotion: PromotionResult | None) -> bool:
    if report.policy_decision is not None and report.policy_decision.action != GovernanceAction.ALLOW:
        return False
    if promotion is not None and promotion.policy_decision is not None and promotion.policy_decision.action != GovernanceAction.ALLOW:
        return False
    if promotion is not None and promotion.side_effect_performed:
        return False
    if report.retry_performed:
        return False
    return report.status == WorkflowExecutionStatus.NEEDS_TEACHER and report.execution_performed


def _compute_next_safe_action(
    *,
    report: WorkflowExecutionReport,
    promotion: PromotionResult | None,
    policy_decision: PolicyDecision | None,
) -> str:
    if policy_decision is not None and policy_decision.requires_human_approval:
        return "request_human_approval"
    if policy_decision is not None and policy_decision.action == GovernanceAction.BLOCK:
        return "stop_budget_exhausted"
    if promotion is not None and promotion.status == PromotionStatus.PROMOTED:
        return "record_lesson_or_continue"
    if promotion is not None and promotion.status in {PromotionStatus.BLOCKED, PromotionStatus.FAILED}:
        return "inspect_promotion_result"
    if report.status == WorkflowExecutionStatus.VERIFIED:
        return "promote_verified_patch"
    if report.status == WorkflowExecutionStatus.NEEDS_TEACHER:
        return "request_teacher_guidance"
    return "inspect_report"


def _render_execution_report_markdown(report: WorkflowExecutionReport) -> str:
    lines = [
        "# Workflow Execution Report",
        "",
        "## Task ID",
        report.task_id,
        "",
        "## Status",
        report.status.value,
        "",
        "## Verification",
        f"- passed: {report.verification_passed}",
        f"- promotion_ready: {report.promotion_ready}",
        f"- command: {report.verification_command or 'None'}",
        "",
        "## Changed Files",
        *_render_bullets(report.changed_files),
        "",
        "## Attempts",
        str(report.attempt_count),
        "",
    ]
    lines.extend(_render_policy_decision_section(report.policy_decision))
    lines.extend(
        [
            "## Action Evidence",
            f"- execution_performed: {report.execution_performed}",
            f"- retry_performed: {report.retry_performed}",
            "",
        ]
    )
    if report.attempt_evidence:
        lines.extend(["## Attempt Evidence"])
        for attempt in report.attempt_evidence:
            lines.extend(
                [
                    f"- attempt_index: {attempt.attempt_index}",
                    f"  - verification_passed: {attempt.verification_passed}",
                    f"  - verification_command: {attempt.verification_command or 'None'}",
                    f"  - teacher_request_id: {attempt.teacher_request_id or 'None'}",
                    f"  - failure_reason: {attempt.failure_reason or 'None'}",
                ]
            )
        lines.append("")
    lines.extend(
        [
            "## Safety",
            f"- source_repo_clean: {report.source_repo_clean}",
            f"- sandbox_removed: {report.sandbox_removed}",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_teacher_guidance_markdown(report: WorkflowExecutionReport) -> str:
    lines = ["# Teacher Guidance", ""]
    for event in report.teacher_guidance_events:
        lines.extend(
            [
                f"## {event.request_id}",
                f"- attempt_index: {event.attempt_index}",
                f"- trigger: {event.trigger}",
                f"- source_bug_dossier_task_id: {event.source_bug_dossier_task_id}",
                "",
                event.guidance,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_promotion_markdown(promotion: PromotionResult) -> str:
    lines = [
        "# Promotion Result",
        "",
        "## Status",
        promotion.status.value,
        "",
        "## Target Branch",
        promotion.target_branch,
        "",
        "## Commit",
        promotion.commit_sha or "None",
        "",
        "## Promoted Files",
        *_render_bullets(promotion.promoted_files),
        "",
        "## Action Evidence",
        f"- side_effect_performed: {promotion.side_effect_performed}",
        "",
        "## Safety",
        f"- source_repo_clean: {promotion.source_repo_clean}",
        f"- promotion_worktree_removed: {promotion.promotion_worktree_removed}",
    ]
    if promotion.rollback_plan or promotion.rollback_ref:
        lines.extend(
            [
                "",
                "## Rollback Plan",
                f"- rollback_ref: {promotion.rollback_ref or 'None'}",
                f"- plan: {promotion.rollback_plan or 'None'}",
            ]
        )
    if promotion.safety_report is not None:
        safety = promotion.safety_report
        lines.extend(
            [
                "",
                "## Promotion Safety Report",
                f"- authorized: {safety.authorized}",
                f"- reasons: {', '.join(safety.reasons) if safety.reasons else 'None'}",
                f"- requested_target_branch: {safety.requested_target_branch}",
                f"- actual_target_branch: {safety.actual_target_branch}",
                f"- approval_applies: {safety.approval_applies}",
                f"- rollback_plan_recorded: {safety.rollback_plan_recorded}",
                f"- rollback_ref: {safety.rollback_ref or 'None'}",
                f"- source_repo_clean_before: {safety.source_repo_clean_before}",
                f"- source_repo_clean_after: {safety.source_repo_clean_after}",
                f"- promoted_ref: {safety.promoted_ref or 'None'}",
                f"- target_ref_verified: {safety.target_ref_verified}",
                f"- promotion_worktree_removed: {safety.promotion_worktree_removed}",
            ]
        )
    if promotion.reason:
        lines.extend(["", "## Reason", promotion.reason])
    lines.extend(_render_policy_decision_section(promotion.policy_decision))
    return "\n".join(lines) + "\n"


def _render_bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _render_policy_decision_section(policy_decision: PolicyDecision | None) -> list[str]:
    if policy_decision is None:
        return ["## Policy Decision", "- None", ""]
    metadata = policy_decision.audit_metadata
    lines = [
        "## Policy Decision",
        f"- action: {policy_decision.action.value}",
        f"- reason: {policy_decision.reason.value}",
        f"- requires_human_approval: {policy_decision.requires_human_approval}",
        f"- message: {policy_decision.message}",
    ]
    for key in sorted(metadata):
        lines.append(f"- {key}: {metadata[key]}")
    lines.append("")
    return lines


class ToyWorkflowExecutor:
    """Provider-free M11 workflow execution loop for controlled toy repos.

    The executor mutates only a detached git worktree sandbox. The source repo is
    inspected after the run but never written to, so promotion remains a separate
    explicit action gated on verifier success.
    """

    def __init__(
        self,
        command_runner: CommandRunner | None = None,
        policy_governor: PolicyGovernor | None = None,
    ) -> None:
        self.command_runner = command_runner or CommandRunner(default_timeout_seconds=120)
        self.policy_governor = policy_governor

    def execute(
        self,
        *,
        source_repo: str | Path,
        contract: TaskContract,
        candidate_writes: list[CandidateFileWrite],
        project_name: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        estimated_tokens: int = 0,
        contains_sensitive_data: bool = False,
        privacy_approved: bool = False,
        worker_retries_used: int = 0,
        teacher_calls_used: int = 0,
    ) -> WorkflowExecutionReport:
        source_path = Path(source_repo)
        policy_decision = self._evaluate_policy(
            task_id=contract.task_id,
            operation="candidate_execution",
            risk_level=risk_level,
            estimated_tokens=estimated_tokens,
            contains_sensitive_data=contains_sensitive_data,
            privacy_approved=privacy_approved,
            worker_retries_used=worker_retries_used,
            teacher_calls_used=teacher_calls_used,
        )
        if policy_decision is not None and policy_decision.action != GovernanceAction.ALLOW:
            return self._policy_blocked_report(
                contract=contract,
                project_name=project_name,
                changed_files=[write.path for write in candidate_writes],
                source_repo=source_path,
                policy_decision=policy_decision,
            )
        sandbox_path: Path | None = None
        changed_files = [write.path for write in candidate_writes]
        report: WorkflowExecutionReport

        with WorktreeSandbox(source_path) as sandbox:
            sandbox_path = sandbox.path
            scope_error = self._validate_scope(contract, candidate_writes)
            if scope_error is not None:
                report = self._blocked_report(
                    contract=contract,
                    project_name=project_name,
                    changed_files=changed_files,
                    reason=scope_error,
                    source_repo=source_path,
                    sandbox_path=sandbox_path,
                )
            else:
                for write in candidate_writes:
                    self._apply_write(sandbox.path, write)

                command, result = self._run_verification(contract, sandbox.path)
                if result.status == CommandStatus.FINISHED and result.exit_code == 0:
                    lesson = self._build_success_lesson(
                        contract=contract,
                        project_name=project_name,
                        verifier=command,
                    )
                    regression_check = build_regression_check_from_lesson(lesson)
                    report = WorkflowExecutionReport(
                        task_id=contract.task_id,
                        status=WorkflowExecutionStatus.VERIFIED,
                        changed_files=changed_files,
                        verification_passed=True,
                        promotion_ready=True,
                        source_repo_clean=self._source_repo_clean(source_path),
                        sandbox_removed=False,
                        verification_command=command,
                        lesson_candidate=lesson,
                        regression_check=regression_check,
                        policy_decision=policy_decision,
                    )
                else:
                    report = self._failure_report(
                        contract=contract,
                        project_name=project_name,
                        changed_files=changed_files,
                        command=command,
                        result=result,
                        source_repo=source_path,
                    )

        report.sandbox_removed = sandbox_path is not None and not sandbox_path.exists()
        report.source_repo_clean = self._source_repo_clean(source_path)
        return report

    def execute_with_teacher_retry(
        self,
        *,
        source_repo: str | Path,
        contract: TaskContract,
        initial_writes: list[CandidateFileWrite],
        teacher_guidance: str | list[str],
        revised_writes: list[CandidateFileWrite] | list[list[CandidateFileWrite]],
        project_name: str,
        max_attempts: int = 2,
        teacher_calls_used: int = 0,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        estimated_tokens: int = 0,
        contains_sensitive_data: bool = False,
        privacy_approved: bool = False,
    ) -> WorkflowExecutionReport:
        """Run bounded provider-free worker attempts with fake teacher guidance.

        The default remains the legacy single retry: one initial attempt plus
        one teacher-guided revised attempt. Callers can supply guidance/writes
        sequences and raise ``max_attempts`` to allow additional bounded rounds.
        Teacher guidance is recorded as evidence only; a report becomes
        promotion-ready only when a verifier-backed attempt passes.
        """
        max_attempts = max(1, max_attempts)
        guidance_rounds = self._normalize_teacher_guidance(teacher_guidance)
        write_rounds = self._normalize_revised_writes(revised_writes)
        teacher_events: list[TeacherGuidanceEvent] = []
        attempt_evidence: list[AttemptEvidence] = []

        current = self.execute(
            source_repo=source_repo,
            contract=contract,
            candidate_writes=initial_writes,
            project_name=project_name,
        )
        current.attempt_count = 1
        attempt_evidence.append(self._build_attempt_evidence(current, attempt_index=1))
        if current.status != WorkflowExecutionStatus.NEEDS_TEACHER or current.bug_dossier is None:
            current.attempt_evidence = attempt_evidence
            return current

        source_bug_dossier_task_id = current.bug_dossier.task_id
        last = current
        retry_budget = max_attempts - 1
        available_retry_rounds = min(retry_budget, len(guidance_rounds), len(write_rounds))

        for retry_index in range(1, available_retry_rounds + 1):
            attempt_index = retry_index + 1
            teacher_policy_decision = self._evaluate_policy(
                task_id=contract.task_id,
                operation="teacher_call",
                risk_level=risk_level,
                estimated_tokens=estimated_tokens,
                contains_sensitive_data=contains_sensitive_data,
                privacy_approved=privacy_approved,
                worker_retries_used=retry_index,
                teacher_calls_used=teacher_calls_used + len(teacher_events),
            )
            if teacher_policy_decision is not None and teacher_policy_decision.action != GovernanceAction.ALLOW:
                last.attempt_count = attempt_index - 1
                last.retry_performed = bool(teacher_events)
                last.policy_decision = teacher_policy_decision
                last.teacher_guidance_events = teacher_events
                last.attempt_evidence = attempt_evidence
                if last.bug_dossier is not None and "policy_gate" not in last.bug_dossier.attempts:
                    last.bug_dossier.attempts.append("policy_gate")
                return last

            event = TeacherGuidanceEvent(
                request_id=f"teacher-request-{contract.task_id}-{retry_index}",
                attempt_index=attempt_index,
                trigger="verifier_failed",
                guidance=guidance_rounds[retry_index - 1],
                source_bug_dossier_task_id=source_bug_dossier_task_id,
            )
            teacher_events.append(event)
            last = self.execute(
                source_repo=source_repo,
                contract=contract,
                candidate_writes=write_rounds[retry_index - 1],
                project_name=project_name,
            )
            last.attempt_count = attempt_index
            last.retry_performed = True
            last.teacher_guidance_events = list(teacher_events)
            attempt_evidence.append(
                self._build_attempt_evidence(
                    last,
                    attempt_index=attempt_index,
                    teacher_request_id=event.request_id,
                )
            )
            last.attempt_evidence = list(attempt_evidence)
            if last.status != WorkflowExecutionStatus.NEEDS_TEACHER or last.bug_dossier is None:
                return last
            retry_label = "retry" if retry_index == 1 else f"retry_{retry_index}"
            if retry_label not in last.bug_dossier.attempts:
                last.bug_dossier.attempts.append(retry_label)
            numbered_retry_label = f"retry_{retry_index}"
            if numbered_retry_label not in last.bug_dossier.attempts:
                last.bug_dossier.attempts.append(numbered_retry_label)

        last.attempt_count = len(attempt_evidence)
        last.retry_performed = bool(teacher_events)
        last.teacher_guidance_events = teacher_events
        last.attempt_evidence = attempt_evidence
        if last.bug_dossier is not None:
            for retry_index in range(1, len(teacher_events) + 1):
                retry_label = "retry" if retry_index == 1 else f"retry_{retry_index}"
                if retry_label not in last.bug_dossier.attempts:
                    last.bug_dossier.attempts.append(retry_label)
                numbered_retry_label = f"retry_{retry_index}"
                if numbered_retry_label not in last.bug_dossier.attempts:
                    last.bug_dossier.attempts.append(numbered_retry_label)
        if last.bug_dossier is not None and available_retry_rounds >= retry_budget:
            last.bug_dossier.teacher_request = (
                f"Diagnose the failed {project_name} worker patch; maximum fake teacher retry attempts exhausted. "
                "Next safe action: hand off bug dossier for human or teacher review without promotion."
            )
        return last

    @staticmethod
    def _normalize_teacher_guidance(teacher_guidance: str | list[str]) -> list[str]:
        if isinstance(teacher_guidance, str):
            return [teacher_guidance]
        return list(teacher_guidance)

    @staticmethod
    def _normalize_revised_writes(
        revised_writes: list[CandidateFileWrite] | list[list[CandidateFileWrite]],
    ) -> list[list[CandidateFileWrite]]:
        if not revised_writes:
            return []
        first_write = revised_writes[0]
        if isinstance(first_write, CandidateFileWrite):
            return [list(revised_writes)]  # type: ignore[list-item]
        return [list(round_writes) for round_writes in revised_writes]  # type: ignore[union-attr]

    @staticmethod
    def _build_attempt_evidence(
        report: WorkflowExecutionReport,
        *,
        attempt_index: int,
        teacher_request_id: str | None = None,
    ) -> AttemptEvidence:
        failure_reason = None
        if not report.verification_passed:
            failure_reason = report.bug_dossier.error_excerpt if report.bug_dossier is not None else report.status.value
        return AttemptEvidence(
            attempt_index=attempt_index,
            changed_files=list(report.changed_files),
            verification_command=report.verification_command,
            verification_passed=report.verification_passed,
            failure_reason=failure_reason,
            teacher_request_id=teacher_request_id,
        )

    def promote_verified_writes(
        self,
        *,
        source_repo: str | Path,
        report: WorkflowExecutionReport,
        candidate_writes: list[CandidateFileWrite],
        target_branch: str,
        commit_message: str,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        estimated_tokens: int = 0,
        contains_sensitive_data: bool = False,
        privacy_approved: bool = False,
        worker_retries_used: int = 0,
        teacher_calls_used: int = 0,
        production_request: ProductionPromotionRequest | None = None,
    ) -> PromotionResult:
        """Promote verifier-approved writes into a dedicated git branch.

        Promotion is deliberately separate from execution. A report must be
        `promotion_ready`; otherwise no branch/worktree is created. When allowed,
        writes are applied in a temporary git worktree for `target_branch`,
        committed there, and the caller's current checkout remains untouched.
        Production promotions opt into an additional fail-closed safety contract
        that records rollback evidence before any git side effect.
        """
        source_path = Path(source_repo)
        safety_report = self._build_initial_promotion_safety_report(
            source_repo=source_path,
            report=report,
            target_branch=target_branch,
            production_request=production_request,
        )
        if safety_report is not None and not safety_report.authorized:
            return PromotionResult(
                status=PromotionStatus.BLOCKED,
                target_branch=target_branch,
                reason=", ".join(safety_report.reasons),
                source_repo_clean=bool(safety_report.source_repo_clean_before),
                promotion_worktree_removed=True,
                rollback_plan=safety_report.rollback_plan,
                rollback_ref=safety_report.rollback_ref,
                safety_report=safety_report,
            )

        if not report.promotion_ready or not report.verification_passed:
            return PromotionResult(
                status=PromotionStatus.BLOCKED,
                target_branch=target_branch,
                reason="report is not promotion-ready",
                source_repo_clean=self._source_repo_clean(source_path),
                promotion_worktree_removed=True,
            )

        policy_decision = self._evaluate_policy(
            task_id=report.task_id,
            operation="promotion",
            risk_level=risk_level,
            estimated_tokens=estimated_tokens,
            contains_sensitive_data=contains_sensitive_data,
            privacy_approved=privacy_approved,
            worker_retries_used=worker_retries_used,
            teacher_calls_used=teacher_calls_used,
        )
        if policy_decision is not None and policy_decision.action != GovernanceAction.ALLOW:
            return PromotionResult(
                status=PromotionStatus.BLOCKED,
                target_branch=target_branch,
                reason=policy_decision.reason.value,
                source_repo_clean=self._source_repo_clean(source_path),
                promotion_worktree_removed=True,
                policy_decision=policy_decision,
                rollback_plan=safety_report.rollback_plan if safety_report else None,
                rollback_ref=safety_report.rollback_ref if safety_report else None,
                safety_report=safety_report,
            )

        promotion_path = Path(tempfile.mkdtemp(prefix="feiyue-promotion-"))
        removed = False
        commit_sha: str | None = None
        try:
            base_sha = safety_report.rollback_ref if safety_report and safety_report.rollback_ref else self._git("rev-parse", "HEAD", cwd=source_path).strip()
            self._git("worktree", "add", "-B", target_branch, str(promotion_path), base_sha, cwd=source_path)
            for write in candidate_writes:
                self._apply_write(promotion_path, write)
            self._git("add", *[write.path for write in candidate_writes], cwd=promotion_path)
            self._git("commit", "-m", commit_message, cwd=promotion_path)
            commit_sha = self._git("rev-parse", "HEAD", cwd=promotion_path).strip()
            if safety_report is not None:
                promoted_ref = self._git("rev-parse", target_branch, cwd=source_path).strip()
                safety_report.promoted_ref = promoted_ref
                safety_report.target_ref_verified = promoted_ref == commit_sha
                if not safety_report.target_ref_verified:
                    safety_report.reasons.append("target_ref_verification_failed")
                    safety_report.authorized = False
                    raise RuntimeError("post-promotion target ref verification failed")
        except Exception as exc:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(promotion_path)],
                cwd=source_path,
                text=True,
                capture_output=True,
                check=False,
            )
            removed = not promotion_path.exists()
            if safety_report is not None:
                safety_report.source_repo_clean_after = self._source_repo_clean(source_path)
                safety_report.promotion_worktree_removed = removed
            return PromotionResult(
                status=PromotionStatus.FAILED,
                target_branch=target_branch,
                commit_sha=commit_sha,
                promoted_files=[write.path for write in candidate_writes],
                reason=str(exc),
                source_repo_clean=self._source_repo_clean(source_path),
                promotion_worktree_removed=removed,
                rollback_plan=safety_report.rollback_plan if safety_report else None,
                rollback_ref=safety_report.rollback_ref if safety_report else None,
                safety_report=safety_report,
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(promotion_path)],
                cwd=source_path,
                text=True,
                capture_output=True,
                check=False,
            )
            removed = not promotion_path.exists()
            if safety_report is not None:
                safety_report.promotion_worktree_removed = removed
                safety_report.source_repo_clean_after = self._source_repo_clean(source_path)

        return PromotionResult(
            status=PromotionStatus.PROMOTED,
            target_branch=target_branch,
            commit_sha=commit_sha,
            promoted_files=[write.path for write in candidate_writes],
            source_repo_clean=self._source_repo_clean(source_path),
            promotion_worktree_removed=removed,
            policy_decision=policy_decision,
            side_effect_performed=True,
            rollback_plan=safety_report.rollback_plan if safety_report else None,
            rollback_ref=safety_report.rollback_ref if safety_report else None,
            safety_report=safety_report,
        )

    def _build_initial_promotion_safety_report(
        self,
        *,
        source_repo: Path,
        report: WorkflowExecutionReport,
        target_branch: str,
        production_request: ProductionPromotionRequest | None,
    ) -> PromotionSafetyReport | None:
        if production_request is None:
            return None

        reasons: list[str] = []
        source_clean_before = self._source_repo_clean(source_repo)
        rollback_plan = production_request.rollback_plan.strip()
        rollback_ref: str | None = None
        if source_clean_before:
            rollback_ref = self._git("rev-parse", "HEAD", cwd=source_repo).strip()

        if production_request.task_id != report.task_id:
            reasons.append("task_id_mismatch")
        if not report.promotion_ready or not report.verification_passed:
            reasons.append("report_not_promotion_ready")
        if production_request.target_branch != target_branch:
            reasons.append("target_branch_mismatch")
        if production_request.allowed_target_branches and target_branch not in production_request.allowed_target_branches:
            reasons.append("target_branch_not_allowed")
        if not source_clean_before:
            reasons.append("source_repo_dirty_before")
        if not rollback_plan:
            reasons.append("rollback_plan_missing")

        approval = production_request.approval_record
        approval_applies = (
            approval is not None
            and approval.task_id == report.task_id
            and approval.approved_action == production_request.required_approval_action
        )
        if not approval_applies:
            reasons.append("missing_or_mismatched_human_approval")

        return PromotionSafetyReport(
            authorized=not reasons,
            reasons=reasons,
            requested_target_branch=production_request.target_branch,
            actual_target_branch=target_branch,
            approval_applies=approval_applies,
            rollback_plan_recorded=bool(rollback_plan and rollback_ref),
            rollback_plan=rollback_plan or None,
            rollback_ref=rollback_ref,
            source_repo_clean_before=source_clean_before,
            promotion_worktree_removed=True,
        )
    def _evaluate_policy(
        self,
        *,
        task_id: str,
        operation: str,
        risk_level: RiskLevel,
        estimated_tokens: int,
        contains_sensitive_data: bool,
        privacy_approved: bool,
        worker_retries_used: int,
        teacher_calls_used: int,
    ) -> PolicyDecision | None:
        if self.policy_governor is None:
            return None
        return self.policy_governor.evaluate(
            PolicyRequest(
                task_id=task_id,
                operation=operation,
                risk_level=risk_level,
                worker_retries_used=worker_retries_used,
                teacher_calls_used=teacher_calls_used,
                estimated_tokens=estimated_tokens,
                contains_sensitive_data=contains_sensitive_data,
                privacy_approved=privacy_approved,
            )
        )

    def _policy_blocked_report(
        self,
        *,
        contract: TaskContract,
        project_name: str,
        changed_files: list[str],
        source_repo: Path,
        policy_decision: PolicyDecision,
    ) -> WorkflowExecutionReport:
        return WorkflowExecutionReport(
            task_id=contract.task_id,
            status=WorkflowExecutionStatus.BLOCKED,
            changed_files=changed_files,
            verification_passed=False,
            promotion_ready=False,
            source_repo_clean=self._source_repo_clean(source_repo),
            sandbox_removed=True,
            policy_decision=policy_decision,
            execution_performed=False,
            retry_performed=False,
            bug_dossier=BugDossier(
                task_id=contract.task_id,
                original_task=contract.render_markdown(),
                changed_files=changed_files,
                failing_command="policy-gate",
                error_excerpt=policy_decision.message,
                attempts=["policy_gate"],
                suspected_cause=f"Policy governor returned {policy_decision.action.value} before execution.",
                teacher_request=f"Review whether {project_name} task policy should be adjusted or manually approved.",
            ),
        )

    def _validate_scope(
        self, contract: TaskContract, candidate_writes: list[CandidateFileWrite]
    ) -> str | None:
        allowed = set(contract.files_to_modify)
        if not allowed:
            return None
        for write in candidate_writes:
            if write.path not in allowed:
                return f"candidate write {write.path} is outside contract scope"
        return None

    @staticmethod
    def _apply_write(sandbox_root: Path, write: CandidateFileWrite) -> None:
        if Path(write.path).is_absolute() or ".." in Path(write.path).parts:
            raise ValueError(f"unsafe candidate write path: {write.path}")
        target = sandbox_root / write.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(write.content, encoding="utf-8")

    def _run_verification(self, contract: TaskContract, sandbox_path: Path) -> tuple[str, CommandResult]:
        command = contract.verification_commands[0] if contract.verification_commands else "python -m pytest -q"
        result = self.command_runner.run(shlex.split(command), cwd=sandbox_path)
        return command, result

    def _blocked_report(
        self,
        *,
        contract: TaskContract,
        project_name: str,
        changed_files: list[str],
        reason: str,
        source_repo: Path,
        sandbox_path: Path,
    ) -> WorkflowExecutionReport:
        return WorkflowExecutionReport(
            task_id=contract.task_id,
            status=WorkflowExecutionStatus.BLOCKED,
            changed_files=changed_files,
            verification_passed=False,
            promotion_ready=False,
            source_repo_clean=self._source_repo_clean(source_repo),
            sandbox_removed=not sandbox_path.exists(),
            bug_dossier=BugDossier(
                task_id=contract.task_id,
                original_task=contract.render_markdown(),
                changed_files=changed_files,
                failing_command="scope-check",
                error_excerpt=reason,
                attempts=["candidate_scope_validation"],
                suspected_cause="Worker attempted to modify a file outside the task contract.",
                teacher_request=f"Review whether {project_name} task scope or worker patch is wrong.",
            ),
        )

    def _failure_report(
        self,
        *,
        contract: TaskContract,
        project_name: str,
        changed_files: list[str],
        command: str,
        result: CommandResult,
        source_repo: Path,
    ) -> WorkflowExecutionReport:
        error_excerpt = (result.stdout + "\n" + result.stderr).strip()
        return WorkflowExecutionReport(
            task_id=contract.task_id,
            status=WorkflowExecutionStatus.NEEDS_TEACHER,
            changed_files=changed_files,
            verification_passed=False,
            promotion_ready=False,
            source_repo_clean=self._source_repo_clean(source_repo),
            sandbox_removed=False,
            verification_command=command,
            bug_dossier=BugDossier(
                task_id=contract.task_id,
                original_task=contract.render_markdown(),
                changed_files=changed_files,
                failing_command=command,
                error_excerpt=error_excerpt,
                attempts=["candidate_patch", command],
                suspected_cause="Candidate patch did not satisfy verifier.",
                teacher_request=f"Diagnose the failed {project_name} worker patch and suggest a narrower retry.",
            ),
        )

    @staticmethod
    def _build_success_lesson(
        *,
        contract: TaskContract,
        project_name: str,
        verifier: str,
    ) -> LessonPacket:
        return LessonPacket(
            lesson_id=f"lesson-{contract.task_id}",
            project=project_name,
            trigger="verified worker patch",
            root_cause="Task contract plus sandbox verifier produced a promotion-ready candidate.",
            prevention_prompt_rule="Keep future worker patches inside the task contract and run the verifier before promotion.",
            verifier=verifier,
            skill_patch_suggestion="Capture this as a provider-free M11 workflow execution example.",
            applies_to=["m11", "workflow-execution", "sandbox-verifier"],
            source_task_id=contract.task_id,
        )

    @staticmethod
    def _git(*args: str, cwd: Path) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout

    @staticmethod
    def _source_repo_clean(source_repo: Path) -> bool:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=source_repo,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout.strip() == ""
