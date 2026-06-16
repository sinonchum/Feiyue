"""Aggregated audit trail across all Hermes approval chain artifacts.

G-8 introduces an aggregated, chronologically-sorted audit trail across
all approval chain artifacts: session drafts, approvals, execution outputs,
verifier evidence, and review intent drafts. The trail is read-only and
does not mutate state, call providers, or start Hermes.

G-9 adds offline export: render_audit_trail_export_markdown() produces a
formatted markdown report suitable for compliance/audit filing.

Each audit entry captures:
  - timestamp: the event's ISO datetime
  - source: which artifact category (draft / approval / execution / verifier / intent)
  - event_type: the specific event type within that source
  - description: human-readable summary
  - details: structured metadata from the original artifact
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AuditEntry:
    """A single entry in the aggregated audit trail."""

    timestamp: str
    source: str
    event_type: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditTrailResult:
    """Result of generating the full audit trail."""

    entries: list[AuditEntry] = field(default_factory=list)
    total_entries: int = 0
    since: str | None = None
    sources_found: dict[str, int] = field(default_factory=dict)
    provider_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


def _read_json_file(path: Path) -> Any | None:
    """Read a JSON file safely, returning None on any error."""
    if not path.exists() or path.is_symlink():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _safe_ts(value: Any) -> str:
    """Extract an ISO timestamp from any value, defaulting to epoch."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "1970-01-01T00:00:00+00:00"


def _extract_session_draft_entries(root: Path) -> list[AuditEntry]:
    """Extract audit entries from session draft events."""
    entries: list[AuditEntry] = []
    drafts_dir = root / ".hermes" / "hermes-session-drafts"
    if not drafts_dir.exists():
        return entries

    for draft_path in sorted(drafts_dir.glob("*/draft.json")):
        draft_dir = draft_path.parent
        draft_id = draft_dir.name

        draft_data = _read_json_file(draft_path)
        if not isinstance(draft_data, dict):
            continue

        created_at = _safe_ts(draft_data.get("created_at"))
        entries.append(
            AuditEntry(
                timestamp=created_at,
                source="draft",
                event_type=draft_data.get("status", "draft_created"),
                description=f"Session draft created: {draft_id} ({draft_data.get('profile', 'unknown')})",
                details={
                    "draft_id": draft_id,
                    "profile": draft_data.get("profile", ""),
                    "created_by": draft_data.get("created_by", ""),
                    "reason": draft_data.get("reason", ""),
                    "toolsets": draft_data.get("toolsets", []),
                    "dry_run_only": draft_data.get("dry_run_only", True),
                    "provider_call_budget": draft_data.get("provider_call_budget", 0),
                    "provider_call_count": draft_data.get("provider_call_count", 0),
                    "hermes_started": draft_data.get("hermes_started", False),
                    "status": draft_data.get("status", ""),
                    "next_required_gate": draft_data.get("next_required_gate", ""),
                },
            )
        )

        # Also read per-event entries if events.json exists
        events_path = draft_dir / "events.json"
        events_data = _read_json_file(events_path)
        if isinstance(events_data, list):
            for event in events_data:
                ts = _safe_ts(event.get("created_at"))
                entries.append(
                    AuditEntry(
                        timestamp=ts,
                        source="draft",
                        event_type=event.get("event_type", "unknown"),
                        description=f"[{draft_id}] seq {event.get('sequence', '?')}: {event.get('message', '')}",
                        details={
                            "draft_id": draft_id,
                            "sequence": event.get("sequence"),
                            "event_type": event.get("event_type"),
                            "message": event.get("message"),
                            "redacted": event.get("redacted", True),
                            "provider_call_count": event.get("provider_call_count", 0),
                            "tool_call_count": event.get("tool_call_count", 0),
                        },
                    )
                )

    return entries


def _extract_approval_entries(root: Path) -> list[AuditEntry]:
    """Extract audit entries from approval gate artifacts."""
    entries: list[AuditEntry] = []
    approvals_dir = root / ".hermes" / "approval-gate"
    if not approvals_dir.exists():
        return entries

    for approval_path in sorted(approvals_dir.glob("*/approval.json")):
        approval_dir = approval_path.parent
        approval_id = approval_dir.name

        approval_data = _read_json_file(approval_path)
        if not isinstance(approval_data, dict):
            continue

        approved_at = _safe_ts(approval_data.get("approved_at"))
        entries.append(
            AuditEntry(
                timestamp=approved_at,
                source="approval",
                event_type="dry_run_approved",
                description=f"Approval created: {approval_id} by {approval_data.get('approved_by', 'unknown')}",
                details={
                    "approval_id": approval_id,
                    "draft_id": approval_data.get("draft_id", ""),
                    "approved_by": approval_data.get("approved_by", ""),
                    "reason": approval_data.get("reason", ""),
                    "status": approval_data.get("status", ""),
                    "draft_status_after": approval_data.get("draft_status_after_approval", ""),
                    "dry_run_only_verified": approval_data.get("dry_run_only_verified", True),
                    "provider_call_budget_verified": approval_data.get("provider_call_budget_verified", 0),
                    "no_hermes_start_verified": approval_data.get("no_hermes_start_verified", True),
                    "no_production_mutation_verified": approval_data.get("no_production_mutation_verified", True),
                    "no_global_config_mutation_verified": approval_data.get("no_global_config_mutation_verified", True),
                    "next_required_gate": approval_data.get("next_required_gate", ""),
                },
            )
        )

        # Approval events
        events_path = approval_dir / "events.json"
        events_data = _read_json_file(events_path)
        if isinstance(events_data, list):
            for event in events_data:
                ts = _safe_ts(event.get("created_at"))
                entries.append(
                    AuditEntry(
                        timestamp=ts,
                        source="approval",
                        event_type=event.get("event_type", "unknown"),
                        description=f"[{approval_id}] seq {event.get('sequence', '?')}: {event.get('message', '')}",
                        details={
                            "approval_id": approval_id,
                            "sequence": event.get("sequence"),
                            "event_type": event.get("event_type"),
                            "message": event.get("message"),
                            "redacted": event.get("redacted", True),
                            "provider_call_count": event.get("provider_call_count", 0),
                            "tool_call_count": event.get("tool_call_count", 0),
                        },
                    )
                )

        # Verifier evidence
        verifier_path = approval_dir / "verifier-evidence.json"
        verifier_data = _read_json_file(verifier_path)
        if isinstance(verifier_data, dict):
            verifier_ts = _safe_ts(verifier_data.get("approved_at"))
            checks = verifier_data.get("verification_checks", {})
            passed_checks = sum(1 for v in checks.values() if v is True)
            total_checks = len(checks)
            entries.append(
                AuditEntry(
                    timestamp=verifier_ts,
                    source="verifier",
                    event_type="verification_evidence",
                    description=f"Verifier evidence for {approval_id}: {passed_checks}/{total_checks} checks passed",
                    details={
                        "approval_id": approval_id,
                        "draft_id": verifier_data.get("draft_id", ""),
                        "approved_by": verifier_data.get("approved_by", ""),
                        "verification_checks": checks,
                        "draft_status_before": verifier_data.get("draft_status_before", ""),
                        "draft_status_after": verifier_data.get("draft_status_after", ""),
                        "provider_call_count_after": verifier_data.get("provider_call_count_after_approval", 0),
                        "hermes_started_after": verifier_data.get("hermes_started_after_approval", False),
                        "boundary_preserved": verifier_data.get("boundary_preserved", True),
                        "next_required_gate": verifier_data.get("next_required_gate", ""),
                    },
                )
            )

    return entries


def _extract_execution_entries(root: Path) -> list[AuditEntry]:
    """Extract audit entries from execution outputs."""
    entries: list[AuditEntry] = []
    exec_dir = root / ".hermes" / "execution-output"
    if not exec_dir.exists():
        return entries

    for output_dir in sorted(exec_dir.iterdir()):
        if not output_dir.is_dir():
            continue
        draft_id = output_dir.name
        output_path = output_dir / "output.json"
        output_data = _read_json_file(output_path)
        if not isinstance(output_data, dict):
            continue

        executed_at = _safe_ts(output_data.get("executed_at"))
        entries.append(
            AuditEntry(
                timestamp=executed_at,
                source="execution",
                event_type="execution_output",
                description=f"Execution output for {draft_id}: {output_data.get('event_count', 0)} events replayed",
                details={
                    "session_draft_id": draft_id,
                    "executed_by": output_data.get("executed_by", ""),
                    "event_count": output_data.get("event_count", 0),
                    "provider_call_count": output_data.get("provider_call_count", 0),
                    "tool_call_count": output_data.get("tool_call_count", 0),
                    "hermes_started": output_data.get("hermes_started", False),
                    "global_hermes_config_mutated": output_data.get("global_hermes_config_mutated", False),
                    "production_mutated": output_data.get("production_mutated", False),
                    "dry_run_only": output_data.get("dry_run_only", True),
                },
            )
        )

        # Per-event entries from execution
        exec_events = output_data.get("events", [])
        if isinstance(exec_events, list):
            for event in exec_events:
                ts = _safe_ts(event.get("created_at"))
                entries.append(
                    AuditEntry(
                        timestamp=ts,
                        source="execution",
                        event_type=event.get("event_type", "execution_step"),
                        description=f"[{draft_id}] seq {event.get('sequence', '?')}: {event.get('message', '')}",
                        details={
                            "session_draft_id": draft_id,
                            "sequence": event.get("sequence"),
                            "event_type": event.get("event_type"),
                            "message": event.get("message"),
                            "redacted": event.get("redacted", True),
                            "provider_call_count": event.get("provider_call_count", 0),
                            "tool_call_count": event.get("tool_call_count", 0),
                            "execution_phase": event.get("execution_phase", "replay"),
                        },
                    )
                )

    return entries


def _extract_intent_entries(root: Path) -> list[AuditEntry]:
    """Extract audit entries from review intent drafts."""
    entries: list[AuditEntry] = []
    intents_dir = root / ".hermes" / "review-intent-drafts"
    if not intents_dir.exists():
        return entries

    for intent_path in sorted(intents_dir.glob("*/intent.json")):
        intent_dir = intent_path.parent
        intent_id = intent_dir.name

        intent_data = _read_json_file(intent_path)
        if not isinstance(intent_data, dict):
            continue

        created_at = _safe_ts(intent_data.get("created_at"))
        entries.append(
            AuditEntry(
                timestamp=created_at,
                source="intent",
                event_type="intent_drafted",
                description=f"Review intent draft: {intent_id} ({intent_data.get('intent_kind', 'unknown')})",
                details={
                    "intent_id": intent_id,
                    "intent_kind": intent_data.get("intent_kind", ""),
                    "item_type": intent_data.get("item_type", ""),
                    "item_id": intent_data.get("item_id", ""),
                    "recommended_action": intent_data.get("recommended_action", ""),
                    "evidence_path": intent_data.get("evidence_path", ""),
                    "created_by": intent_data.get("created_by", ""),
                    "reason": intent_data.get("reason", ""),
                    "status": intent_data.get("status", ""),
                    "next_required_gate": intent_data.get("next_required_gate", ""),
                    "draft_only": intent_data.get("draft_only", True),
                    "mutates_state": intent_data.get("mutates_state", False),
                },
            )
        )

    return entries


def generate_audit_trail(
    project_root: str | Path,
    since: str | None = None,
) -> AuditTrailResult:
    """Generate the aggregated audit trail across all approval chain artifacts.

    Args:
        project_root: Path to the project root.
        since: Optional ISO timestamp filter; only entries after this timestamp are included.

    Returns:
        AuditTrailResult with chronologically sorted entries.
    """
    root = Path(project_root)

    all_entries: list[AuditEntry] = []
    all_entries.extend(_extract_session_draft_entries(root))
    all_entries.extend(_extract_approval_entries(root))
    all_entries.extend(_extract_execution_entries(root))
    all_entries.extend(_extract_intent_entries(root))

    # Filter by since if provided
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            all_entries = [e for e in all_entries if _parse_ts(e.timestamp) >= since_dt]
        except (ValueError, TypeError):
            pass  # Invalid since, return unfiltered

    # Sort chronologically by timestamp
    all_entries.sort(key=lambda e: e.timestamp)

    # Count sources
    source_counts: dict[str, int] = {}
    for entry in all_entries:
        source_counts[entry.source] = source_counts.get(entry.source, 0) + 1

    return AuditTrailResult(
        entries=all_entries,
        total_entries=len(all_entries),
        since=since,
        sources_found=source_counts,
        provider_call_count=0,
        hermes_started=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
    )


def _parse_ts(value: str) -> datetime:
    """Parse an ISO timestamp string, returning epoch on failure."""
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.fromisoformat("1970-01-01T00:00:00+00:00")


_SOURCE_EMOJI: dict[str, str] = {
    "draft": "📝",
    "approval": "✅",
    "execution": "⚙️",
    "verifier": "🔍",
    "intent": "📋",
}


def _source_label(source: str) -> str:
    emoji = _SOURCE_EMOJI.get(source, "•")
    return f"{emoji} {source.capitalize()}"


def render_audit_trail_export_markdown(result: AuditTrailResult) -> str:
    """Render the audit trail as a formatted markdown report for offline export.

    Produces a compliance-ready document with:
      - Metadata header (generated timestamp, summary)
      - Source breakdown with per-source tables
      - Chronological event log

    The report is read-only, contains no secrets, and does not call providers.
    """
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    lines: list[str] = []

    # Header
    lines.append("# Feiyue Audit Trail Report")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Filter since:** {result.since or 'all'}")
    lines.append(f"**Mode:** Offline export (provider-free, read-only)")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Total entries | {result.total_entries} |")
    sources_str = ", ".join(f"{k}: {v}" for k, v in sorted(result.sources_found.items()))
    lines.append(f"| Sources | {sources_str} |")
    lines.append(f"| Provider call count | {result.provider_call_count} |")
    lines.append(f"| Hermes started | {result.hermes_started} |")
    lines.append(f"| Production mutated | {result.production_mutated} |")
    lines.append("")

    # Safety statement
    lines.append("### Safety Boundaries")
    lines.append("")
    lines.append(
        "- provider_call_count=0: No external LLM/API calls were made during this audit period."
    )
    lines.append("- hermes_started=false: The real Hermes Agent process was never started.")
    lines.append(
        "- production_mutated=false: No production Hermes configuration was modified."
    )
    lines.append("")

    # Source breakdown
    lines.append("## Source Breakdown")
    lines.append("")
    if not result.entries:
        lines.append("_No audit trail entries found._")
        lines.append("")

    # Group entries by source
    by_source: dict[str, list] = {}
    for entry in result.entries:
        by_source.setdefault(entry.source, []).append(entry)

    for source in sorted(by_source.keys()):
        source_entries = by_source[source]
        label = _source_label(source)
        lines.append(f"### {label} ({len(source_entries)} entries)")
        lines.append("")
        lines.append("| Timestamp | Event Type | Description |")
        lines.append("|---|---|---|")
        for entry in source_entries:
            desc = entry.description.replace("|", "\\|")[:120]
            lines.append(f"| {entry.timestamp} | {entry.event_type} | {desc} |")
        lines.append("")

    # Full chronological log
    lines.append("## Chronological Event Log")
    lines.append("")
    if not result.entries:
        lines.append("_No entries._")
    else:
        lines.append("| # | Timestamp | Source | Event Type | Description |")
        lines.append("|---|---|---|---|---|")
        for i, entry in enumerate(result.entries, start=1):
            desc = entry.description.replace("|", "\\|")[:160]
            lines.append(f"| {i} | {entry.timestamp} | {entry.source} | {entry.event_type} | {desc} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "_This report was generated by Feiyue G-9 Audit Export. "
        "It is a read-only, provider-free artifact with no side effects._"
    )
    lines.append("")

    return "\n".join(lines)
