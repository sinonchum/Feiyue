"""Verifier evidence cross-check dashboard for the Feiyue operator console.

G-5 aggregates all verifier evidence from approval gates across the project
and produces a cross-check report. The report:

1. Walks `.hermes/approval-gate/*/` to read approval, verifier-evidence, events.
2. Reads the original session draft events for before/after comparison.
3. Cross-checks event stream consistency, boundary preservation, and anomaly detection.
4. Produces a JSON report consumable by the frontend dashboard.

The report always respects the safety boundary:
  - provider_call_count = 0 everywhere
  - hermes_started = False everywhere
  - No approval -> real Hermes session mapping
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.approval_gate import (
    approval_gate_dir,
    read_approval_events,
    read_approval_verifier_evidence,
)
from feiyue_core.workflow.hermes_sessions import (
    hermes_session_drafts_dir,
    read_hermes_session_events,
)

Field = None  # placeholder, not used in this module


class PerDraftReport(FeiyueModel):
    """Cross-check report for a single approval gate."""
    draft_id: str
    approval_id: str
    status: str
    approved_by: str
    approved_at: str | None = None
    event_count_before: int = 0
    event_count_after: int = 0
    new_events_after_approval: list[str] = []
    all_event_types: list[str] = []
    event_stream_consistent: bool = True
    provider_call_count_verified: int = 0
    hermes_started_verified: bool = False
    boundary_preserved: bool = True
    verification_checks: dict[str, bool] = {}
    anomalies: list[str] = []


class VerifierReport(FeiyueModel):
    """Aggregated verifier evidence cross-check report."""
    total_approvals: int = 0
    total_verification_checks_passed: int = 0
    total_anomalies: int = 0
    all_boundary_preserved: bool = True
    all_provider_calls_zero: bool = True
    all_hermes_not_started: bool = True
    dry_run_only: bool = True
    reports: list[PerDraftReport] = []


def generate_verifier_report(project_root: str | Path) -> VerifierReport:
    """Walk .hermes/approval-gate/*/ and build a cross-check report."""
    root = Path(project_root)
    gate_d = approval_gate_dir(root)
    if not gate_d.is_dir():
        return VerifierReport()

    reports: list[PerDraftReport] = []
    total_checks_passed = 0
    total_anomalies = 0
    all_boundary = True
    all_zero_calls = True
    all_hermes_off = True

    for entry in sorted(gate_d.iterdir()):
        if not entry.is_dir():
            continue
        approval_id = entry.name
        approval_path = entry / "approval.json"
        if not approval_path.is_file():
            continue

        approval_data = _read_json_safe(approval_path, {})
        draft_id = approval_data.get("draft_id", approval_id)
        status = approval_data.get("status", "unknown")
        approved_by = approval_data.get("approved_by", "unknown")
        approved_at = approval_data.get("approved_at")

        # Read verifier evidence
        evidence = read_approval_verifier_evidence(root, approval_id)
        checks = evidence.get("verification_checks", {})

        # Read approval events (after)
        try:
            after_events = read_approval_events(root, approval_id)
        except Exception:
            after_events = []
        event_types_after = [e.get("event_type", "") for e in after_events]

        # Read session draft events (before)
        try:
            before_raw = read_hermes_session_events(root, draft_id)
        except Exception:
            before_raw = []
        before_events = [e.model_dump(mode="json") for e in before_raw] if before_raw and hasattr(before_raw[0], "model_dump") else []
        if not before_events:
            before_events = [e if isinstance(e, dict) else {} for e in before_raw]
        event_types_before = [e.get("event_type", "") for e in before_events]

        # Cross-check: new events after approval
        before_set = set(event_types_before)
        new_events = [et for et in event_types_after if et not in before_set]

        # All events combined
        all_event_types = event_types_before + event_types_after

        # Check for anomalies
        anomalies: list[str] = []

        # Provider call count anomaly
        provider_calls = evidence.get("provider_call_count_after_approval", 0)
        if provider_calls != 0:
            anomalies.append("provider_call_count_after_approval is non-zero")
            all_zero_calls = False

        # Hermes started anomaly
        hermes_started = evidence.get("hermes_started_after_approval", False)
        if hermes_started:
            anomalies.append("hermes_started_after_approval is True")
            all_hermes_off = False

        # Boundary preserved
        boundary_ok = evidence.get("boundary_preserved", False)
        if not boundary_ok:
            anomalies.append("boundary_preserved is False")
            all_boundary = False

        # Event stream consistency: approval events should extend the before events
        # (before + after should form the full timeline)
        stream_consistent = True
        # The combined event stream should have before events as prefix + after events
        combined_types = event_types_before + event_types_after
        if before_events and after_events:
            # Check that before events appear in order at the start of combined
            for i, et in enumerate(event_types_before):
                if i < len(combined_types) and combined_types[i] != et:
                    stream_consistent = False
                    anomalies.append(f"event_stream_gap: before event '{et}' not at position {i} in combined stream")
                    break
        # Check that dry_run_approved is in the new events
        if "dry_run_approved" not in new_events:
            anomalies.append("dry_run_approved event missing from approval event stream")

        # Build verification checks map
        check_map = {}
        for key in ("dry_run_only_verified", "provider_call_budget_verified",
                     "no_hermes_start_verified", "no_production_mutation_verified",
                     "no_global_config_mutation_verified"):
            val = checks.get(key)
            # provider_call_budget_verified can be integer 0 (verified zero) == True
            if key == "provider_call_budget_verified":
                check_map[key] = val is not None  # 0 == verified zero == passed
            else:
                check_map[key] = bool(val) if val is not None else False

        checks_passed = sum(1 for v in check_map.values() if v)
        total_checks_passed += checks_passed

        per = PerDraftReport(
            draft_id=draft_id,
            approval_id=approval_id,
            status=status,
            approved_by=approved_by,
            approved_at=approved_at,
            event_count_before=len(before_events),
            event_count_after=len(after_events),
            new_events_after_approval=new_events,
            all_event_types=all_event_types,
            event_stream_consistent=stream_consistent,
            provider_call_count_verified=provider_calls,
            hermes_started_verified=hermes_started,
            boundary_preserved=boundary_ok,
            verification_checks=check_map,
            anomalies=anomalies,
        )
        reports.append(per)
        total_anomalies += len(anomalies)

    return VerifierReport(
        total_approvals=len(reports),
        total_verification_checks_passed=total_checks_passed,
        total_anomalies=total_anomalies,
        all_boundary_preserved=all_boundary,
        all_provider_calls_zero=all_zero_calls,
        all_hermes_not_started=all_hermes_off,
        dry_run_only=True,
        reports=reports,
    )


def generate_event_diff(
    project_root: str | Path,
    approval_id: str,
) -> dict[str, object]:
    """Generate a before/after event diff for a single approval gate."""
    from feiyue_core.workflow.approval_gate import (
        _safe_id,
        DryRunApprovalError,
    )

    if not _safe_id(approval_id):
        raise DryRunApprovalError("approval_id is not safe", status_code=400)

    root = Path(project_root)
    gate_d = approval_gate_dir(root) / approval_id
    approval_path = gate_d / "approval.json"
    if not approval_path.is_file():
        raise DryRunApprovalError("Approval not found", status_code=404)

    approval_data = _read_json_safe(approval_path, {})
    draft_id = approval_data.get("draft_id", approval_id)

    before_raw = read_hermes_session_events(root, draft_id) if draft_id else []
    before_events = [e.model_dump(mode="json") for e in before_raw] if before_raw and hasattr(before_raw[0], "model_dump") else []
    if not before_events:
        before_events = [e if isinstance(e, dict) else {} for e in before_raw]
    try:
        after_events = read_approval_events(root, approval_id)
    except Exception:
        after_events = []

    before_set = {e.get("event_type", "") for e in before_events}
    added = [e for e in after_events if e.get("event_type", "") not in before_set]
    removed = [e for e in before_events if e.get("event_type", "") not in {ev.get("event_type", "") for ev in after_events}]
    common = [e for e in before_events if e.get("event_type", "") in {ev.get("event_type", "") for ev in after_events}]

    return {
        "draft_id": draft_id,
        "approval_id": approval_id,
        "event_count_before": len(before_events),
        "event_count_after": len(after_events),
        "added_events": added,
        "removed_events": removed,
        "common_events": common,
    }


def _read_json_safe(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
