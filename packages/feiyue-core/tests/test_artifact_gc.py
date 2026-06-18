from __future__ import annotations

import os
import time
from pathlib import Path

from feiyue_core.workflow.artifact_gc import get_cleanup_status, run_cleanup


def _write_artifact(root: Path, relative_dir: str, *, age_days: int) -> Path:
    artifact_dir = root / ".hermes" / relative_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = artifact_dir / "output.json"
    payload.write_text('{"status": "ok", "created_by": "test"}', encoding="utf-8")
    old_timestamp = time.time() - age_days * 86400
    os.utime(payload, (old_timestamp, old_timestamp))
    os.utime(artifact_dir, (old_timestamp, old_timestamp))
    return artifact_dir


def test_cleanup_status_is_read_only_and_reports_no_mutation(tmp_path: Path) -> None:
    old_artifact = _write_artifact(tmp_path, "execution-output/old-run", age_days=10)
    active_artifact = _write_artifact(tmp_path, "frontend-dogfood/active-run", age_days=1)

    status = get_cleanup_status(tmp_path, ttl_days=7)

    assert status.total_artifacts == 2
    assert status.expired_artifacts == 1
    assert status.active_artifacts == 1
    assert status.mutates_state is False
    assert status.provider_call_count == 0
    assert status.hermes_started is False
    assert old_artifact.exists()
    assert active_artifact.exists()


def test_cleanup_run_reports_project_local_mutation_and_removes_only_expired_artifacts(tmp_path: Path) -> None:
    old_artifact = _write_artifact(tmp_path, "execution-output/old-run", age_days=10)
    active_artifact = _write_artifact(tmp_path, "frontend-dogfood/active-run", age_days=1)
    config = tmp_path / ".hermes" / "config.yaml"
    config.write_text("must: stay\n", encoding="utf-8")

    result = run_cleanup(tmp_path, ttl_days=7)

    assert result.mutates_state is True
    assert result.provider_call_count == 0
    assert result.hermes_started is False
    assert result.removed_count == 1
    assert result.kept_count == 1
    assert result.remaining_artifacts == 1
    assert result.removed_entries == [
        {
            "path": ".hermes/execution-output/old-run",
            "category": "execution outputs",
            "age_days": 10.0,
            "size_bytes": 38,
        }
    ]
    assert not old_artifact.exists()
    assert active_artifact.exists()
    assert config.read_text(encoding="utf-8") == "must: stay\n"
