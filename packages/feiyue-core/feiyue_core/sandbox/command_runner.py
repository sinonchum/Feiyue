from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class CommandStatus(StrEnum):
    FINISHED = "finished"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CommandResult(FeiyueModel):
    command: list[str]
    cwd: str
    status: CommandStatus
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = Field(ge=0)


class CommandRunner:
    def __init__(self, default_timeout_seconds: int = 60) -> None:
        self.default_timeout_seconds = default_timeout_seconds

    def run(
        self,
        command: Sequence[str],
        cwd: str | Path,
        timeout_seconds: int | None = None,
    ) -> CommandResult:
        started = time.monotonic()
        command_list = [str(part) for part in command]
        cwd_path = Path(cwd)
        timeout = timeout_seconds or self.default_timeout_seconds
        try:
            completed = subprocess.run(
                command_list,
                cwd=cwd_path,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            status = CommandStatus.FINISHED if completed.returncode == 0 else CommandStatus.FAILED
            return CommandResult(
                command=command_list,
                cwd=str(cwd_path),
                status=status,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=self._duration_ms(started),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command_list,
                cwd=str(cwd_path),
                status=CommandStatus.TIMEOUT,
                exit_code=None,
                stdout=self._coerce_output(exc.stdout),
                stderr=self._coerce_output(exc.stderr),
                duration_ms=self._duration_ms(started),
            )

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, int((time.monotonic() - started) * 1000))

    @staticmethod
    def _coerce_output(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
