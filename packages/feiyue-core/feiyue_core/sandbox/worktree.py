from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from types import TracebackType

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class WorktreeSandbox(FeiyueModel):
    repo_path: Path
    path: Path = Field(default_factory=Path)
    head_sha: str = ""
    keep_on_exit: bool = False

    def __init__(self, repo_path: str | Path, keep_on_exit: bool = False) -> None:
        super().__init__(repo_path=Path(repo_path), keep_on_exit=keep_on_exit)

    def __enter__(self) -> "WorktreeSandbox":
        self.repo_path = self.repo_path.resolve()
        self.head_sha = self._git("rev-parse", "HEAD", cwd=self.repo_path).strip()
        self.path = Path(tempfile.mkdtemp(prefix="feiyue-worktree-"))
        self._git("worktree", "add", "--detach", str(self.path), self.head_sha, cwd=self.repo_path)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.keep_on_exit:
            return
        if self.path:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self.path)],
                cwd=self.repo_path,
                text=True,
                capture_output=True,
                check=False,
            )
            if self.path.exists():
                shutil.rmtree(self.path, ignore_errors=True)

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
