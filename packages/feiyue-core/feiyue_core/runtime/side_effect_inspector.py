from __future__ import annotations

import hashlib
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class SideEffectStatus(StrEnum):
    CONFIRMED = "confirmed"
    NEEDS_INSPECTION = "needs_inspection"
    UNSAFE_TO_REPEAT = "unsafe_to_repeat"


class SideEffectCheck(FeiyueModel):
    subject: str
    status: SideEffectStatus
    reason: str
    observed: dict[str, Any] = Field(default_factory=dict)


class SideEffectInspector:
    def inspect(self, spec: dict[str, Any]) -> SideEffectCheck:
        check_type = spec.get("type")
        if check_type == "file_hash":
            return self.check_file_hash(spec["path"], spec["expected_sha256"])
        if check_type == "artifact_exists":
            return self.check_artifact_exists(spec["path"])
        if check_type == "git_ref":
            return self.check_git_ref(spec["repo_path"], spec["ref"], spec["expected_sha"])
        return SideEffectCheck(
            subject=str(spec.get("subject", "unknown")),
            status=SideEffectStatus.NEEDS_INSPECTION,
            reason=f"unsupported side effect check type: {check_type}",
            observed={"spec_type": check_type},
        )

    def check_file_hash(self, path: str | Path, expected_sha256: str) -> SideEffectCheck:
        file_path = Path(path)
        if not file_path.exists():
            return SideEffectCheck(
                subject=str(file_path),
                status=SideEffectStatus.NEEDS_INSPECTION,
                reason="file missing",
                observed={"exists": False},
            )
        actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual == expected_sha256:
            return SideEffectCheck(
                subject=str(file_path),
                status=SideEffectStatus.CONFIRMED,
                reason="file hash matches",
                observed={"exists": True, "sha256": actual},
            )
        return SideEffectCheck(
            subject=str(file_path),
            status=SideEffectStatus.NEEDS_INSPECTION,
            reason="file hash mismatch",
            observed={"exists": True, "sha256": actual, "expected_sha256": expected_sha256},
        )

    def check_artifact_exists(self, path: str | Path) -> SideEffectCheck:
        artifact_path = Path(path)
        exists = artifact_path.exists()
        return SideEffectCheck(
            subject=str(artifact_path),
            status=SideEffectStatus.CONFIRMED if exists else SideEffectStatus.NEEDS_INSPECTION,
            reason="artifact exists" if exists else "artifact missing",
            observed={"exists": exists},
        )

    def check_git_ref(self, repo_path: str | Path, ref: str, expected_sha: str) -> SideEffectCheck:
        repo = Path(repo_path)
        completed = subprocess.run(
            ["git", "rev-parse", ref],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            return SideEffectCheck(
                subject=f"{repo}:{ref}",
                status=SideEffectStatus.NEEDS_INSPECTION,
                reason="git ref unavailable",
                observed={"exit_code": completed.returncode, "stderr": completed.stderr},
            )
        actual = completed.stdout.strip()
        if actual == expected_sha:
            return SideEffectCheck(
                subject=f"{repo}:{ref}",
                status=SideEffectStatus.CONFIRMED,
                reason="git ref matches",
                observed={"sha": actual},
            )
        return SideEffectCheck(
            subject=f"{repo}:{ref}",
            status=SideEffectStatus.UNSAFE_TO_REPEAT,
            reason="git ref mismatch",
            observed={"sha": actual, "expected_sha": expected_sha},
        )
