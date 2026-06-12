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
        if check_type == "git_remote_ref":
            return self.check_git_remote_ref(spec["remote_url"], spec["ref"], spec["expected_sha"])
        if check_type == "github_ref":
            return self.check_github_ref(spec["repo"], spec["ref"], spec["expected_sha"])
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

    def check_git_remote_ref(self, remote_url: str, ref: str, expected_sha: str) -> SideEffectCheck:
        completed = subprocess.run(
            ["git", "ls-remote", remote_url, ref],
            text=True,
            capture_output=True,
            check=False,
        )
        subject = f"{remote_url}:{ref}"
        if completed.returncode != 0:
            return SideEffectCheck(
                subject=subject,
                status=SideEffectStatus.NEEDS_INSPECTION,
                reason="git remote ref unavailable",
                observed={"exit_code": completed.returncode, "stderr": completed.stderr},
            )
        output = completed.stdout.strip()
        if not output:
            return SideEffectCheck(
                subject=subject,
                status=SideEffectStatus.NEEDS_INSPECTION,
                reason="git remote ref missing",
                observed={"exists": False},
            )
        actual = output.split()[0]
        if actual == expected_sha:
            return SideEffectCheck(
                subject=subject,
                status=SideEffectStatus.CONFIRMED,
                reason="git remote ref matches",
                observed={"sha": actual},
            )
        return SideEffectCheck(
            subject=subject,
            status=SideEffectStatus.UNSAFE_TO_REPEAT,
            reason="git remote ref mismatch",
            observed={"sha": actual, "expected_sha": expected_sha},
        )

    def check_github_ref(self, repo: str, ref: str, expected_sha: str) -> SideEffectCheck:
        api_ref = ref.removeprefix("refs/")
        completed = subprocess.run(
            ["gh", "api", f"repos/{repo}/git/ref/{api_ref}", "--jq", ".object.sha"],
            text=True,
            capture_output=True,
            check=False,
        )
        subject = f"github:{repo}:{ref}"
        if completed.returncode != 0:
            return SideEffectCheck(
                subject=subject,
                status=SideEffectStatus.NEEDS_INSPECTION,
                reason="github ref unavailable",
                observed={"exit_code": completed.returncode, "stderr": completed.stderr},
            )
        actual = completed.stdout.strip()
        if not actual:
            return SideEffectCheck(
                subject=subject,
                status=SideEffectStatus.NEEDS_INSPECTION,
                reason="github ref missing",
                observed={"exists": False},
            )
        if actual == expected_sha:
            return SideEffectCheck(
                subject=subject,
                status=SideEffectStatus.CONFIRMED,
                reason="github ref matches",
                observed={"sha": actual},
            )
        return SideEffectCheck(
            subject=subject,
            status=SideEffectStatus.UNSAFE_TO_REPEAT,
            reason="github ref mismatch",
            observed={"sha": actual, "expected_sha": expected_sha},
        )
