"""Execution output for approved Hermes dry-run session drafts.

G-7 introduces a two-phase execution model for approved dry-run session
drafts: draft → approval → execute (no provider). The "execution" replays
the approval event stream as execution output, keeping provider_call_count=0,
hermes_started=false, and no production mutation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class ExecutionRequest(FeiyueModel):
    executed_by: str = "operator"
    reason: str = "operator_executed_approved_dry_run"


class ExecutionOutput(FeiyueModel):
    session_draft_id: str
    executed_by: str
    executed_at: str
    events: list[dict[str, Any]] = Field(default_factory=list)
    event_count: int = 0
    provider_call_count: int = 0
    tool_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    dry_run_only: bool = True


class ExecutionOutputSummary(FeiyueModel):
    outputs: list[ExecutionOutput] = Field(default_factory=list)
    dry_run_only: bool = True
    provider_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


class ExecutionOutputError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        self.status_code = status_code
        super().__init__(message)


_EXECUTION_DIR = Path(".hermes") / "execution-output"


def _execution_dir(root: str | Path, draft_id: str) -> Path:
    return Path(root) / _EXECUTION_DIR / draft_id


def _read_draft(root: str | Path, draft_id: str) -> dict[str, Any] | None:
    draft_path = list(Path(root).rglob(f".hermes/hermes-session-drafts/{draft_id}/draft.json"))
    if not draft_path:
        return None
    try:
        data = json.loads(draft_path[0].read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def execute_approved_dry_run(
    root: str | Path,
    draft_id: str,
    request: ExecutionRequest,
) -> ExecutionOutput:
    """Execute an approved dry-run session draft (no provider, replay events)."""
    root = Path(root)
    draft_data = _read_draft(root, draft_id)
    if draft_data is None:
        raise ExecutionOutputError(f"no session draft found: {draft_id}", 404)

    status = draft_data.get("status", "")
    if status != "approved_dry_run":
        raise ExecutionOutputError(
            f"draft {draft_id} has status {status!r}, expected 'approved_dry_run'",
            400,
        )

    # Read approval events to replay as execution output
    approval_events_path = root / ".hermes" / "approval-gate" / draft_id / "events.json"
    if approval_events_path.exists():
        try:
            approval_events = json.loads(approval_events_path.read_text(encoding="utf-8"))
        except Exception:
            approval_events = []
    else:
        approval_events = []

    # Generate execution events by replaying approval events with execution metadata
    now = datetime.now(UTC).isoformat()
    execution_events = []
    for seq, event in enumerate(approval_events, start=1):
        execution_events.append({
            "sequence": seq,
            "event_type": event.get("event_type", "execution_step"),
            "message": event.get("message", ""),
            "redacted": event.get("redacted", True),
            "provider_call_count": 0,
            "tool_call_count": 0,
            "created_at": now,
            "execution_phase": "replay",
        })

    # Build output
    output = ExecutionOutput(
        session_draft_id=draft_id,
        executed_by=request.executed_by,
        executed_at=now,
        events=execution_events,
        event_count=len(execution_events),
        provider_call_count=0,
        tool_call_count=0,
        hermes_started=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        dry_run_only=True,
    )

    # Write execution output to project-local .hermes dir
    out_dir = _execution_dir(root, draft_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "output.json").write_text(
        json.dumps(output.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output


def list_execution_outputs(root: str | Path) -> ExecutionOutputSummary:
    """List all execution outputs."""
    root = Path(root)
    base_dir = root / _EXECUTION_DIR
    if not base_dir.exists():
        return ExecutionOutputSummary()

    outputs = []
    for entry_dir in sorted(base_dir.iterdir()):
        if not entry_dir.is_dir():
            continue
        output_path = entry_dir / "output.json"
        if not output_path.exists():
            continue
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
            outputs.append(ExecutionOutput.model_validate(data))
        except Exception:
            pass

    return ExecutionOutputSummary(
        outputs=outputs,
        dry_run_only=True,
        provider_call_count=0,
        hermes_started=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
    )


def read_execution_output(root: str | Path, draft_id: str) -> ExecutionOutput:
    """Read a single execution output."""
    output_path = _execution_dir(root, draft_id) / "output.json"
    if not output_path.exists():
        raise ExecutionOutputError(f"no execution output found: {draft_id}", 404)
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        return ExecutionOutput.model_validate(data)
    except Exception as exc:
        raise ExecutionOutputError(f"invalid execution output: {exc}", 500) from exc
