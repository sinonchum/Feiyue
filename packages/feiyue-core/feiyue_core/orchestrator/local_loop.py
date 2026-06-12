from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pydantic import Field

from feiyue_core.audit import JsonlTraceWriter
from feiyue_core.recovery import OperationRiskLevel, RecoveryManifest
from feiyue_core.runtime import OperationRecorder, SessionJournal
from feiyue_core.sandbox import WorktreeSandbox
from feiyue_core.sandbox.command_runner import CommandRunner
from feiyue_core.schemas import (
    Candidate,
    CandidateStatus,
    ExecutionRun,
    ExecutionStatus,
    TaskSpec,
    TraceEvent,
    TraceEventType,
    VerificationResult,
)
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.verifiers import PytestVerifier


class LocalLoopResult(FeiyueModel):
    task: TaskSpec
    candidate: Candidate
    execution: ExecutionRun
    verification: VerificationResult
    trace_refs: list[str] = Field(default_factory=list)


class LocalLoopInterrupted(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__(f"local loop interrupted after {stage}")
        self.stage = stage


class LocalLoop:
    def __init__(
        self,
        trace_path: str | Path,
        journal_path: str | Path | None = None,
        interrupt_after: str | None = None,
    ) -> None:
        self.trace_path = Path(trace_path)
        self.trace_writer = JsonlTraceWriter(self.trace_path)
        self.journal = SessionJournal(journal_path) if journal_path is not None else None
        self.operation_recorder = OperationRecorder(self.journal) if self.journal is not None else None
        self.interrupt_after = interrupt_after
        self.command_runner = CommandRunner(default_timeout_seconds=120)
        self.verifier = PytestVerifier(self.command_runner)

    def run(self, repo_path: str | Path, task: TaskSpec, candidate: Candidate) -> LocalLoopResult:
        self._initialize_manifest(task, candidate)
        operation_id = f"local_loop:{task.id}:{candidate.id}"
        if self.operation_recorder is not None:
            self.operation_recorder.register(
                operation_id=operation_id,
                tool="local_loop",
                args={"task_id": task.id, "candidate_id": candidate.id},
                risk_level=OperationRiskLevel.MEDIUM,
                preconditions={"repo_path": str(repo_path)},
            )
        self._maybe_interrupt("operation_registered")
        with WorktreeSandbox(repo_path) as sandbox:
            self._write_event(
                task.id,
                TraceEventType.TOOL_OPERATION_STARTED,
                "sandbox created",
                {"candidate_id": candidate.id, "sandbox_path": str(sandbox.path)},
            )
            self._maybe_interrupt("sandbox_created")
            self._apply_file_writes(sandbox.path, candidate)
            self._maybe_interrupt("file_writes")
            verification = self.verifier.verify(sandbox.path)
            self._maybe_interrupt("verification")
            execution = self._execution_from_verification(candidate, verification)
            candidate.status = CandidateStatus.VERIFIED if verification.passed else CandidateStatus.FAILED
            self._write_event(
                task.id,
                TraceEventType.TOOL_OPERATION_FINISHED,
                "pytest verification completed",
                {
                    "candidate_id": candidate.id,
                    "execution_id": execution.id,
                    "passed": verification.passed,
                    "exit_code": execution.exit_code,
                },
            )
            if self.operation_recorder is not None:
                self.operation_recorder.finish(
                    operation_id=operation_id,
                    postconditions={"passed": verification.passed, "exit_code": execution.exit_code},
                    artifact_refs=[str(self.trace_path)],
                )
                self._update_manifest_after_result(task, candidate, execution, verification)
            return LocalLoopResult(
                task=task,
                candidate=candidate,
                execution=execution,
                verification=verification,
                trace_refs=[str(self.trace_path)],
            )

    def _initialize_manifest(self, task: TaskSpec, candidate: Candidate) -> None:
        if self.journal is None:
            return
        manifest = RecoveryManifest(
            session_id=task.id,
            current_goal=task.goal,
            task_id=task.id,
            confirmed_facts=[f"candidate {candidate.id} selected for local verification"],
            changed_files=sorted(str(path) for path in candidate.metadata.get("file_writes", {}).keys()),
            next_safe_action="run candidate in isolated worktree and verify with pytest",
        )
        self.journal.write_manifest(manifest)

    def _update_manifest_after_result(
        self,
        task: TaskSpec,
        candidate: Candidate,
        execution: ExecutionRun,
        verification: VerificationResult,
    ) -> None:
        if self.journal is None:
            return
        manifest = self.journal.read_manifest()
        completed = f"candidate {candidate.id} verification completed"
        if completed not in manifest.completed_steps:
            manifest.completed_steps.append(completed)
        manifest.verified_outputs.append(
            f"operation {execution.id} {'passed' if verification.passed else 'failed'} for candidate {candidate.id}"
        )
        manifest.next_safe_action = "promote candidate" if verification.passed else "inspect pytest failure output"
        self.journal.write_manifest(manifest)

    @staticmethod
    def _apply_file_writes(sandbox_path: Path, candidate: Candidate) -> None:
        file_writes = candidate.metadata.get("file_writes", {})
        for relative_path, content in file_writes.items():
            target = sandbox_path / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")

    @staticmethod
    def _execution_from_verification(candidate: Candidate, verification: VerificationResult) -> ExecutionRun:
        status = ExecutionStatus.FINISHED if verification.passed else ExecutionStatus.FAILED
        exit_code = verification.metadata.get("exit_code")
        duration_ms = verification.metadata.get("duration_ms")
        command = " ".join(verification.metadata.get("command", ["python3", "-m", "pytest", "-q"]))
        return ExecutionRun(
            id=f"run_{uuid4().hex}",
            candidate_id=candidate.id,
            status=status,
            command=command,
            exit_code=exit_code,
            duration_ms=duration_ms,
            artifact_refs=[],
        )

    def _write_event(
        self,
        session_id: str,
        event_type: TraceEventType,
        message: str,
        data: dict[str, object],
    ) -> None:
        self.trace_writer.append(
            TraceEvent(
                id=f"evt_{uuid4().hex}",
                session_id=session_id,
                type=event_type,
                message=message,
                data=data,
            )
        )

    def _maybe_interrupt(self, stage: str) -> None:
        if self.interrupt_after == stage:
            raise LocalLoopInterrupted(stage)
