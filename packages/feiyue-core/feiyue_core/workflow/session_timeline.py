"""Session replay timeline — full lifecycle visualization for a single draft.

G-11 adds a per-draft session timeline endpoint that aggregates all lifecycle
events across every stage: draft creation, events, approval, verifier checks,
execution output. Returns a chronologically-sorted timeline with phase labels.

Safety boundaries: provider-free, no Hermes start, no production mutation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TimelineEvent:
    """A single event in the session lifecycle timeline."""

    phase: str
    """Lifecycle phase: draft, approval, verifier, execution."""

    timestamp: str
    """ISO 8601 timestamp."""

    event_type: str
    """Machine-readable event type (e.g. session_draft_created, dry_run_approved)."""

    summary: str
    """Human-readable one-line summary."""

    status: str
    """Status label for the timeline node: active, done, blocked."""

    details: dict[str, Any] = field(default_factory=dict)
    """Additional structured metadata."""


@dataclass
class SessionTimelineResult:
    """Result of a session timeline query."""

    draft_id: str
    events: list[TimelineEvent]
    total_phases: int
    total_events: int
    current_status: str
    provider_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    dry_run_only: bool = True


def generate_session_timeline(
    project_root: str | Path,
    draft_id: str,
) -> SessionTimelineResult:
    """Aggregate all lifecycle events for a specific session draft.

    Scans draft events, approval events, verifier evidence, and execution
    output to build a complete chronological timeline.

    Returns an empty events list if the draft does not exist.
    """
    root = Path(project_root)
    events: list[TimelineEvent] = []
    current_status = "unknown"

    # --- Phase 1: Draft ---
    draft_path = root / ".hermes" / "hermes-session-drafts" / draft_id / "draft.json"
    events_path = root / ".hermes" / "hermes-session-drafts" / draft_id / "events.json"

    if draft_path.exists():
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            current_status = draft.get("status", "unknown")
            events.append(
                TimelineEvent(
                    phase="draft",
                    timestamp=draft.get("created_at", "unknown"),
                    event_type="session_draft_created",
                    summary=f"Session draft created by {draft.get('created_by', 'unknown')}",
                    status="done",
                    details={
                        "profile": draft.get("profile", ""),
                        "status": draft.get("status", ""),
                        "goal_hash": draft.get("goal_hash", ""),
                        "toolsets": draft.get("toolsets", []),
                    },
                )
            )
        except (json.JSONDecodeError, OSError):
            pass

        if events_path.exists():
            try:
                raw_events = json.loads(events_path.read_text(encoding="utf-8"))
                for ev in raw_events:
                    events.append(
                        TimelineEvent(
                            phase="draft",
                            timestamp=ev.get("created_at", "unknown"),
                            event_type=ev.get("event_type", "unknown"),
                            summary=ev.get("message", ""),
                            status="done",
                            details={
                                "sequence": ev.get("sequence", 0),
                                "provider_call_count": ev.get("provider_call_count", 0),
                                "tool_call_count": ev.get("tool_call_count", 0),
                            },
                        )
                    )
            except (json.JSONDecodeError, OSError):
                pass

    # --- Phase 2: Approval ---
    approval_path = root / ".hermes" / "approval-gate" / draft_id / "approval.json"
    approval_events_path = root / ".hermes" / "approval-gate" / draft_id / "events.json"

    if approval_path.exists():
        try:
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            status_before = approval.get("draft_status_before_approval", "")
            status_after = approval.get("draft_status_after_approval", "")
            events.append(
                TimelineEvent(
                    phase="approval",
                    timestamp=approval.get("approved_at", "unknown"),
                    event_type="dry_run_approved",
                    summary=f"Approved by {approval.get('approved_by', 'unknown')}: "
                    f"{status_before} → {status_after}",
                    status="done",
                    details={
                        "approved_by": approval.get("approved_by", ""),
                        "reason": approval.get("reason", ""),
                        "dry_run_only_verified": approval.get("dry_run_only_verified", False),
                        "provider_call_budget_verified": approval.get("provider_call_budget_verified", 0),
                    },
                )
            )
            if status_after == "approved_dry_run":
                current_status = "approved_dry_run"
        except (json.JSONDecodeError, OSError):
            pass

        if approval_events_path.exists():
            try:
                raw_events = json.loads(approval_events_path.read_text(encoding="utf-8"))
                for ev in raw_events:
                    events.append(
                        TimelineEvent(
                            phase="approval",
                            timestamp=ev.get("created_at", "unknown"),
                            event_type=ev.get("event_type", "unknown"),
                            summary=ev.get("message", ""),
                            status="done",
                            details={
                                "sequence": ev.get("sequence", 0),
                                "provider_call_count": ev.get("provider_call_count", 0),
                            },
                        )
                    )
            except (json.JSONDecodeError, OSError):
                pass

    # --- Phase 3: Verifier ---
    verifier_path = root / ".hermes" / "approval-gate" / draft_id / "verifier-evidence.json"
    if verifier_path.exists():
        try:
            verifier = json.loads(verifier_path.read_text(encoding="utf-8"))
            checks = verifier.get("verification_checks", {})
            check_summary = ", ".join(f"{k}={v}" for k, v in checks.items())
            events.append(
                TimelineEvent(
                    phase="verifier",
                    timestamp=verifier.get("approved_at", "unknown"),
                    event_type="verifier_evidence_checked",
                    summary=f"Verification checks: {check_summary}",
                    status="done",
                    details={
                        "boundary_preserved": verifier.get("boundary_preserved", False),
                        "provider_call_count_after_approval": verifier.get("provider_call_count_after_approval", 0),
                        "hermes_started_after_approval": verifier.get("hermes_started_after_approval", False),
                        "checks": checks,
                    },
                )
            )
        except (json.JSONDecodeError, OSError):
            pass

    # --- Phase 4: Execution ---
    exec_path = root / ".hermes" / "execution-output" / draft_id / "output.json"
    if exec_path.exists():
        try:
            output = json.loads(exec_path.read_text(encoding="utf-8"))
            events.append(
                TimelineEvent(
                    phase="execution",
                    timestamp=output.get("executed_at", "unknown"),
                    event_type="execution_completed",
                    summary=f"Executed by {output.get('executed_by', 'unknown')}: "
                    f"{output.get('event_count', 0)} events replayed",
                    status="done",
                    details={
                        "executed_by": output.get("executed_by", ""),
                        "event_count": output.get("event_count", 0),
                        "provider_call_count": output.get("provider_call_count", 0),
                        "tool_call_count": output.get("tool_call_count", 0),
                    },
                )
            )
            for ev in output.get("events", []):
                events.append(
                    TimelineEvent(
                        phase="execution",
                        timestamp=ev.get("created_at", "unknown"),
                        event_type=ev.get("event_type", "replay_event"),
                        summary=f"[replay] {ev.get('message', '')}",
                        status="done",
                        details={
                            "sequence": ev.get("sequence", 0),
                            "execution_phase": ev.get("execution_phase", "replay"),
                            "provider_call_count": ev.get("provider_call_count", 0),
                        },
                    )
                )
            if current_status != "approved_dry_run":
                current_status = "executed"
        except (json.JSONDecodeError, OSError):
            pass

    # Sort by timestamp chronologically
    events.sort(
        key=lambda e: (
            _parse_ts_for_sort(e.timestamp),
            {"draft": 0, "approval": 1, "verifier": 2, "execution": 3}.get(e.phase, 99),
        )
    )

    phase_count = len({e.phase for e in events})

    return SessionTimelineResult(
        draft_id=draft_id,
        events=events,
        total_phases=phase_count,
        total_events=len(events),
        current_status=current_status,
    )


def _parse_ts_for_sort(value: str) -> datetime:
    """Parse ISO timestamp for sorting, returning epoch on failure."""
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.fromisoformat("1970-01-01T00:00:00+00:00")
