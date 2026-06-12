from __future__ import annotations

import shlex
import subprocess
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
    def _source_repo_clean(source_repo: Path) -> bool:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=source_repo,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout.strip() == ""
