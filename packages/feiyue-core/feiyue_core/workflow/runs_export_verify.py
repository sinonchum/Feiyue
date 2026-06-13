from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class StaticRunsReportVerification:
    valid: bool
    checked_files: int
    issues: list[str]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_hash(path: Path, expected: str, label: str, issues: list[str]) -> None:
    if not path.exists():
        issues.append(f"missing file: {label}")
        return
    if _sha256(path) != expected:
        issues.append(f"sha256 mismatch: {label}")


def _check_source_hash(path: Path, expected: str, label: str, issues: list[str]) -> None:
    if not path.exists():
        issues.append(f"missing source evidence: {label}")
        return
    if _sha256(path) != expected:
        issues.append(f"source evidence sha256 mismatch: {label}")


def verify_static_runs_report(manifest_path: str | Path) -> StaticRunsReportVerification:
    """Verify a static run report manifest against exported files and source evidence."""

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    report_root = manifest_file.parent
    project_root = Path(manifest["project_root"])
    issues: list[str] = []
    checked_files = 0

    for file_entry in manifest.get("files", []):
        rel_path = file_entry["path"]
        checked_files += 1
        _check_hash(report_root / rel_path, file_entry["sha256"], rel_path, issues)

    for run_entry in manifest.get("runs", []):
        detail_path = run_entry["detail_path"]
        checked_files += 1
        _check_hash(report_root / detail_path, run_entry["detail_sha256"], detail_path, issues)

        source_path = run_entry["source_evidence_path"]
        checked_files += 1
        _check_source_hash(
            project_root / source_path,
            run_entry["source_evidence_sha256"],
            source_path,
            issues,
        )

    return StaticRunsReportVerification(valid=not issues, checked_files=checked_files, issues=issues)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs-export-verify",
        description="Verify Feiyue static run report manifest hashes.",
    )
    parser.add_argument("manifest", help="Path to static report manifest.json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = verify_static_runs_report(args.manifest)
    if result.valid:
        print(f"STATIC_REPORT_VERIFY_OK checked_files={result.checked_files}")
        return 0
    print(f"STATIC_REPORT_VERIFY_FAILED checked_files={result.checked_files}")
    for issue in result.issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
