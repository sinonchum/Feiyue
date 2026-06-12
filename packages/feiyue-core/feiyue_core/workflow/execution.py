from __future__ import annotations

import shlex
import subprocess
import tempfile
from enum import StrEnum
from pathlib import Path

from pydantic import Field

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


class TeacherGuidanceEvent(FeiyueModel):
    """Auditable fake-teacher guidance used between worker attempts."""

    request_id: str
    trigger: str
    guidance: str
    source_bug_dossier_task_id: str


class PromotionResult(FeiyueModel):
    """Result of promoting a verified workflow patch into a target branch."""

    status: PromotionStatus
    target_branch: str
    commit_sha: str | None = None
    promoted_files: list[str] = Field(default_factory=list)
    reason: str | None = None
    source_repo_clean: bool
    promotion_worktree_removed: bool


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


class WorkflowReportArtifacts(FeiyueModel):
    """File paths created by WorkflowReportWriter."""

    run_dir: Path
    execution_json_path: Path
    execution_markdown_path: Path
    bug_dossier_markdown_path: Path | None = None
    teacher_guidance_markdown_path: Path | None = None
    promotion_json_path: Path | None = None
    promotion_markdown_path: Path | None = None


class WorkflowReportWriter:
    """Persist M11 workflow reports under .hermes/runs/<task_id>."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def write(
        self,
        *,
        report: WorkflowExecutionReport,
        promotion: PromotionResult | None = None,
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

        return WorkflowReportArtifacts(
            run_dir=run_dir,
            execution_json_path=execution_json_path,
            execution_markdown_path=execution_markdown_path,
            bug_dossier_markdown_path=bug_path,
            teacher_guidance_markdown_path=teacher_path,
            promotion_json_path=promotion_json_path,
            promotion_markdown_path=promotion_markdown_path,
        )


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
        "## Safety",
        f"- source_repo_clean: {report.source_repo_clean}",
        f"- sandbox_removed: {report.sandbox_removed}",
    ]
    return "\n".join(lines) + "\n"


def _render_teacher_guidance_markdown(report: WorkflowExecutionReport) -> str:
    lines = ["# Teacher Guidance", ""]
    for event in report.teacher_guidance_events:
        lines.extend(
            [
                f"## {event.request_id}",
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
        "## Safety",
        f"- source_repo_clean: {promotion.source_repo_clean}",
        f"- promotion_worktree_removed: {promotion.promotion_worktree_removed}",
    ]
    if promotion.reason:
        lines.extend(["", "## Reason", promotion.reason])
    return "\n".join(lines) + "\n"


def _render_bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


class ToyWorkflowExecutor:
    """Provider-free M11 workflow execution loop for controlled toy repos.

    The executor mutates only a detached git worktree sandbox. The source repo is
    inspected after the run but never written to, so promotion remains a separate
    explicit action gated on verifier success.
    """

    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self.command_runner = command_runner or CommandRunner(default_timeout_seconds=120)

    def execute(
        self,
        *,
        source_repo: str | Path,
        contract: TaskContract,
        candidate_writes: list[CandidateFileWrite],
        project_name: str,
    ) -> WorkflowExecutionReport:
        source_path = Path(source_repo)
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
        teacher_guidance: str,
        revised_writes: list[CandidateFileWrite],
        project_name: str,
    ) -> WorkflowExecutionReport:
        """Run one worker attempt, request fake teacher guidance, then retry once.

        This is still provider-free: the caller supplies deterministic teacher
        guidance and revised writes. The method records the teacher event as
        guidance only; success remains gated by the verifier on the retry.
        """
        first = self.execute(
            source_repo=source_repo,
            contract=contract,
            candidate_writes=initial_writes,
            project_name=project_name,
        )
        if first.status != WorkflowExecutionStatus.NEEDS_TEACHER or first.bug_dossier is None:
            first.attempt_count = 1
            return first

        event = TeacherGuidanceEvent(
            request_id=f"teacher-request-{contract.task_id}-1",
            trigger="verifier_failed",
            guidance=teacher_guidance,
            source_bug_dossier_task_id=first.bug_dossier.task_id,
        )
        retry = self.execute(
            source_repo=source_repo,
            contract=contract,
            candidate_writes=revised_writes,
            project_name=project_name,
        )
        retry.attempt_count = 2
        retry.teacher_guidance_events = [event]
        if retry.bug_dossier is not None and "retry" not in retry.bug_dossier.attempts:
            retry.bug_dossier.attempts.append("retry")
        return retry

    def promote_verified_writes(
        self,
        *,
        source_repo: str | Path,
        report: WorkflowExecutionReport,
        candidate_writes: list[CandidateFileWrite],
        target_branch: str,
        commit_message: str,
    ) -> PromotionResult:
        """Promote verifier-approved writes into a dedicated git branch.

        Promotion is deliberately separate from execution. A report must be
        `promotion_ready`; otherwise no branch/worktree is created. When allowed,
        writes are applied in a temporary git worktree for `target_branch`,
        committed there, and the caller's current checkout remains untouched.
        """
        source_path = Path(source_repo)
        if not report.promotion_ready or not report.verification_passed:
            return PromotionResult(
                status=PromotionStatus.BLOCKED,
                target_branch=target_branch,
                reason="report is not promotion-ready",
                source_repo_clean=self._source_repo_clean(source_path),
                promotion_worktree_removed=True,
            )

        promotion_path = Path(tempfile.mkdtemp(prefix="feiyue-promotion-"))
        removed = False
        try:
            base_sha = self._git("rev-parse", "HEAD", cwd=source_path).strip()
            self._git("worktree", "add", "-B", target_branch, str(promotion_path), base_sha, cwd=source_path)
            for write in candidate_writes:
                self._apply_write(promotion_path, write)
            self._git("add", *[write.path for write in candidate_writes], cwd=promotion_path)
            self._git("commit", "-m", commit_message, cwd=promotion_path)
            commit_sha = self._git("rev-parse", "HEAD", cwd=promotion_path).strip()
        except Exception as exc:
            return PromotionResult(
                status=PromotionStatus.FAILED,
                target_branch=target_branch,
                promoted_files=[write.path for write in candidate_writes],
                reason=str(exc),
                source_repo_clean=self._source_repo_clean(source_path),
                promotion_worktree_removed=removed,
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

        return PromotionResult(
            status=PromotionStatus.PROMOTED,
            target_branch=target_branch,
            commit_sha=commit_sha,
            promoted_files=[write.path for write in candidate_writes],
            source_repo_clean=self._source_repo_clean(source_path),
            promotion_worktree_removed=removed,
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
