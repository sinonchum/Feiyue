from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from pydantic import Field

from feiyue_core.recovery import OperationRiskLevel, RecoveryManifest
from feiyue_core.schemas.common import FeiyueModel

from .journal import SessionJournal
from .operation_recorder import OperationRecorder
from .resume_flow import ResumeFlow


class InterruptionSimulationResult(FeiyueModel):
    manifest: RecoveryManifest
    recovery_prompt: str
    warnings: list[str] = Field(default_factory=list)
    file_path: Path
    artifact_path: Path
    git_repo_path: Path


def simulate_interrupted_resume(root: str | Path) -> InterruptionSimulationResult:
    """Run a deterministic local interruption/resume simulation.

    This is intentionally provider-free: it records three side effects before they
    happen, performs them, then resumes with a fresh flow that only reads durable
    journal/manifest state.
    """
    base = Path(root)
    journal = SessionJournal(base / "session.jsonl")
    journal.write_manifest(
        RecoveryManifest(
            session_id="sim_interrupted_resume",
            current_goal="prove interrupted side effects reconcile from durable state",
            next_safe_action="resume from manifest",
        )
    )
    recorder = OperationRecorder(journal)

    file_path = base / "outputs" / "state.txt"
    artifact_path = base / "artifacts" / "report.json"
    git_repo = _init_git_repo(base / "repo")
    expected_head = _git(git_repo, "rev-parse", "HEAD").stdout.strip()

    recorder.register(
        operation_id="op_file_sim",
        tool="write_file",
        args={"path": str(file_path), "content": "stable output\n"},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"stage": "before file write"},
    )
    recorder.register(
        operation_id="op_artifact_sim",
        tool="generate_artifact",
        args={"artifact_path": str(artifact_path)},
        risk_level=OperationRiskLevel.MEDIUM,
        preconditions={"stage": "before artifact write"},
    )
    recorder.register(
        operation_id="op_git_sim",
        tool="git_push",
        args={"repo_path": str(git_repo), "ref": "HEAD", "expected_sha": expected_head},
        risk_level=OperationRiskLevel.HIGH,
        preconditions={"local_head": expected_head},
    )

    # Simulate side effects completing just before the process/model disappears.
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("stable output\n", encoding="utf-8")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text('{"ok": true}\n', encoding="utf-8")

    # Fresh ResumeFlow: no OperationRecorder in-memory records are reused.
    context = ResumeFlow(journal=journal).prepare()
    return InterruptionSimulationResult(
        manifest=context.manifest,
        recovery_prompt=context.recovery_prompt,
        warnings=context.warnings,
        file_path=file_path,
        artifact_path=artifact_path,
        git_repo_path=git_repo,
    )


def _init_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "initial")
    return path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def build_demo_summary(result: InterruptionSimulationResult) -> dict[str, object]:
    return {
        "pending_operations": result.manifest.pending_operations,
        "warnings": result.warnings,
        "next_safe_action": result.manifest.next_safe_action,
        "verified_count": len(result.manifest.verified_outputs),
        "verified_outputs": result.manifest.verified_outputs,
        "file_path": str(result.file_path),
        "artifact_path": str(result.artifact_path),
        "git_repo_path": str(result.git_repo_path),
        "file_exists": result.file_path.exists(),
        "artifact_exists": result.artifact_path.exists(),
        "recovery_prompt": result.recovery_prompt,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Feiyue's deterministic interruption/resume demo.")
    parser.add_argument("--root", required=True, help="Directory where demo state will be created.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable JSON summary.")
    args = parser.parse_args(argv)

    result = simulate_interrupted_resume(args.root)
    summary = build_demo_summary(result)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    print("Feiyue interruption/resume demo completed")
    print(f"pending_operations: {summary['pending_operations']}")
    print(f"warnings: {summary['warnings']}")
    print(f"next_safe_action: {summary['next_safe_action']}")
    print(f"verified_count: {summary['verified_count']}")
    print(f"file_path: {summary['file_path']}")
    print(f"artifact_path: {summary['artifact_path']}")
    print(f"git_repo_path: {summary['git_repo_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
