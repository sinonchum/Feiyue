from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pydantic import Field

from feiyue_core.audit import JsonlTraceWriter
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


class LocalLoop:
    def __init__(self, trace_path: str | Path) -> None:
        self.trace_path = Path(trace_path)
        self.trace_writer = JsonlTraceWriter(self.trace_path)
        self.command_runner = CommandRunner(default_timeout_seconds=120)
        self.verifier = PytestVerifier(self.command_runner)

    def run(self, repo_path: str | Path, task: TaskSpec, candidate: Candidate) -> LocalLoopResult:
        with WorktreeSandbox(repo_path) as sandbox:
            self._write_event(
                task.id,
                TraceEventType.TOOL_OPERATION_STARTED,
                "sandbox created",
                {"candidate_id": candidate.id, "sandbox_path": str(sandbox.path)},
            )
            self._apply_file_writes(sandbox.path, candidate)
            verification = self.verifier.verify(sandbox.path)
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
            return LocalLoopResult(
                task=task,
                candidate=candidate,
                execution=execution,
                verification=verification,
                trace_refs=[str(self.trace_path)],
            )

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
