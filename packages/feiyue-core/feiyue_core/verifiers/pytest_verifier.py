from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from feiyue_core.sandbox.command_runner import CommandRunner, CommandStatus
from feiyue_core.schemas import VerificationResult, VerifierType


class PytestVerifier:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self.command_runner = command_runner or CommandRunner(default_timeout_seconds=120)

    def verify(self, project_dir: str | Path) -> VerificationResult:
        command = ["python3", "-m", "pytest", "-q"]
        result = self.command_runner.run(command, cwd=project_dir)
        passed = result.status == CommandStatus.FINISHED and result.exit_code == 0
        if result.status == CommandStatus.TIMEOUT:
            failure_category = "pytest_timeout"
        elif passed:
            failure_category = None
        else:
            failure_category = "pytest_failed"
        return VerificationResult(
            id=f"vr_{uuid4().hex}",
            execution_run_id=f"command:{' '.join(command)}",
            verifier_type=VerifierType.PYTEST,
            verifier_name="pytest",
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            evidence_refs=[],
            failure_category=failure_category,
            metadata={
                "command": result.command,
                "exit_code": result.exit_code,
                "status": result.status.value,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_ms": result.duration_ms,
            },
        )
