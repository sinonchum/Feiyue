"""Artifact garbage collection — TTL-based cleanup of old .hermes/ artifacts.

G-12 adds configurable TTL-based garbage collection for all .hermes/ artifact
directories: hermes-session-drafts, approval-gate, execution-output,
review-intent-drafts, and frontend-dogfood.

Provides:
- get_cleanup_status(project_root): Scans all artifacts and reports age,
  total count, and what would be cleaned with a given TTL without mutating.
- run_cleanup(project_root, ttl_days=7): Physically removes artifacts older
  than ttl_days. Returns a report of what was removed.

Safety: provider-free, no Hermes start, no global config mutation.
The status scan is read-only; the cleanup run is an explicit project-local
artifact mutation because it removes expired directories under .hermes/.
It never touches config.yaml, .env, model-routing.yaml, or any file outside
.hermes/.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ARTIFACT_DIRS = [
    ("hermes-session-drafts", "session drafts"),
    ("approval-gate", "approval gates"),
    ("execution-output", "execution outputs"),
    ("review-intent-drafts", "review intent drafts"),
    ("frontend-dogfood", "frontend dogfood runs"),
]

_SAFE_FILE_EXTENSIONS = {".json", ".yaml", ".yml", ".md", ".txt"}


@dataclass
class ArtifactEntry:
    """A single artifact in a cleanup scan."""

    path: str
    """Relative path under .hermes/."""

    category: str
    """Artifact category label."""

    age_days: float
    """Age in days since last modification."""

    size_bytes: int
    """Total size of the artifact directory."""

    status: str
    """Current status: active (within TTL) or expired (beyond TTL)."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Optional metadata from the artifact's JSON payload."""


@dataclass
class CleanupStatusResult:
    """Report from get_cleanup_status — read-only, no mutation."""

    total_artifacts: int = 0
    expired_artifacts: int = 0
    active_artifacts: int = 0
    total_size_bytes: int = 0
    expired_size_bytes: int = 0
    artifacts: list[ArtifactEntry] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    ttl_days: int = 7
    mutates_state: bool = False
    provider_call_count: int = 0
    hermes_started: bool = False


@dataclass
class CleanupRunResult:
    """Report from run_cleanup — what was removed."""

    removed_count: int = 0
    removed_size_bytes: int = 0
    kept_count: int = 0
    remaining_artifacts: int = 0
    removed_entries: list[dict[str, object]] = field(default_factory=list)
    kept_entries: list[dict[str, object]] = field(default_factory=list)
    ttl_days: int = 7
    mutates_state: bool = True
    provider_call_count: int = 0
    hermes_started: bool = False


def _artifact_age_days(path: Path) -> float:
    """Compute age in days since last modification."""
    try:
        mtime = path.stat().st_mtime
        now = time.time()
        return (now - mtime) / 86400.0
    except OSError:
        return float("inf")


def _artifact_size(path: Path) -> int:
    """Compute total size of a directory or file."""
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except OSError:
        pass
    return total


def _read_artifact_meta(path: Path) -> dict[str, Any]:
    """Read the first JSON file in an artifact directory for metadata."""
    try:
        json_files = sorted(path.glob("*.json"))
        if json_files:
            data = json.loads(json_files[0].read_text(encoding="utf-8"))
            return {
                "created_at": data.get("created_at", data.get("approved_at", data.get("executed_at", ""))),
                "status": data.get("status", "unknown"),
                "created_by": data.get("created_by", data.get("approved_by", data.get("executed_by", ""))),
            }
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _scan_hermes_hermes(root: Path) -> list[ArtifactEntry]:
    """Scan .hermes/hermes/ artifacts (nested hermes subdir)."""
    entries: list[ArtifactEntry] = []
    hermes_root = root / ".hermes" / "hermes"
    if not hermes_root.exists():
        return entries
    for category_dir in hermes_root.iterdir():
        if not category_dir.is_dir():
            continue
        category_label = category_dir.name
        for artifact_dir in category_dir.iterdir():
            if not artifact_dir.is_dir():
                continue
            age = _artifact_age_days(artifact_dir)
            size = _artifact_size(artifact_dir)
            meta = _read_artifact_meta(artifact_dir)
            entries.append(
                ArtifactEntry(
                    path=artifact_dir.relative_to(root).as_posix(),
                    category=category_label,
                    age_days=round(age, 1),
                    size_bytes=size,
                    status="expired" if age > 30 else "active",
                    meta=meta,
                )
            )
    return entries


def get_cleanup_status(project_root: str | Path, ttl_days: int = 7) -> CleanupStatusResult:
    """Scan all artifact directories and report age/expiry status.

    Pure read-only operation: no mutation, no provider calls, no Hermes start.
    """
    root = Path(project_root)
    hermes_root = root / ".hermes"
    entries: list[ArtifactEntry] = []

    for subdir, label in _ARTIFACT_DIRS:
        artifact_dir = hermes_root / subdir
        if not artifact_dir.exists():
            continue
        for entry_dir in artifact_dir.iterdir():
            if not entry_dir.is_dir():
                continue
            age = _artifact_age_days(entry_dir)
            size = _artifact_size(entry_dir)
            meta = _read_artifact_meta(entry_dir)
            entries.append(
                ArtifactEntry(
                    path=entry_dir.relative_to(root).as_posix(),
                    category=label,
                    age_days=round(age, 1),
                    size_bytes=size,
                    status="expired" if age > ttl_days else "active",
                    meta=meta,
                )
            )

    # Also scan nested .hermes/hermes/ artifacts
    entries.extend(_scan_hermes_hermes(root))

    total_size = sum(e.size_bytes for e in entries)
    expired = [e for e in entries if e.status == "expired"]
    expired_size = sum(e.size_bytes for e in expired)

    categories: dict[str, int] = {}
    for e in entries:
        categories[e.category] = categories.get(e.category, 0) + 1

    return CleanupStatusResult(
        total_artifacts=len(entries),
        expired_artifacts=len(expired),
        active_artifacts=len(entries) - len(expired),
        total_size_bytes=total_size,
        expired_size_bytes=expired_size,
        artifacts=sorted(entries, key=lambda e: e.age_days, reverse=True),
        categories=categories,
        ttl_days=ttl_days,
    )


def run_cleanup(project_root: str | Path, ttl_days: int = 7) -> CleanupRunResult:
    """Remove artifact directories older than ttl_days.

    Returns a report of what was removed and what was kept.
    Only removes expired artifact directories — never touches
    config.yaml, .env, model-routing.yaml, or files outside .hermes/.
    """
    status = get_cleanup_status(project_root, ttl_days=ttl_days)
    removed: list[dict[str, object]] = []
    kept: list[dict[str, object]] = []
    removed_size = 0

    for entry in status.artifacts:
        full_path = Path(project_root) / entry.path
        if entry.status == "expired":
            try:
                size = _artifact_size(full_path)
                if full_path.is_dir():
                    shutil.rmtree(full_path)
                else:
                    full_path.unlink()
                removed.append({
                    "path": entry.path,
                    "category": entry.category,
                    "age_days": entry.age_days,
                    "size_bytes": size,
                })
                removed_size += size
            except OSError:
                kept.append({
                    "path": entry.path,
                    "category": entry.category,
                    "age_days": entry.age_days,
                    "reason": "failed_to_remove",
                })
        else:
            kept.append({
                "path": entry.path,
                "category": entry.category,
                "age_days": entry.age_days,
                "reason": "within_ttl",
            })

    remaining = sum(1 for e in status.artifacts if e.status == "active")

    return CleanupRunResult(
        removed_count=len(removed),
        removed_size_bytes=removed_size,
        kept_count=len(kept),
        remaining_artifacts=remaining,
        removed_entries=removed,
        kept_entries=kept,
        ttl_days=ttl_days,
    )
