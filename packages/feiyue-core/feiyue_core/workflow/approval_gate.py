"""Exact approval gate for Hermes dry-run session drafts.

G-4 introduces the concept of an exact approval gate. An operator explicitly
approves a specific session draft for dry-run execution. The approval records
the exact draft_id, verifier identity, and reason, and the draft transitions
from "blocked_until_exact_approval" to "approved_dry_run".

Even approved drafts stay at:
  - provider_call_count = 0
  - tool_call_count = 0
  - hermes_started = False

A verifier evidence artifact is written alongside the approval so the Feiyue
operator console can display the approval chain without exposing the raw draft.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel


class DryRunApprovalRequest(FeiyueModel):
    """Request to approve a specific session draft for dry-run execution."""

    draft_id: str
    approved_by: str = "operator"
    reason: str = "operator_approved_dry_run_execution"
    dry_run_only_verified: bool = True
    provider_call_budget_verified: int = 0
    profile_verified: str = ""
    toolsets_verified: list[str] = Field(default_factory=list)
    no_hermes_start_verified: bool = True
    no_production_mutation_verified: bool = True
    no_global_config_mutation_verified: bool = True

    @field_validator("draft_id", "approved_by", "reason")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field must be non-empty")
        return text

    @field_validator("dry_run_only_verified")
    @classmethod
    def _must_be_dry_run(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("G-4 dry-run approval requires dry_run_only_verified=True")
        return value

    @field_validator("provider_call_budget_verified")
    @classmethod
    def _no_provider_budget(cls, value: int) -> int:
        if value != 0:
            raise ValueError("G-4 dry-run approval requires provider_call_budget_verified=0")
        return value

    @field_validator("no_hermes_start_verified")
    @classmethod
    def _no_hermes(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("G-4 dry-run approval requires no_hermes_start_verified=True")
        return value

    @field_validator("no_production_mutation_verified")
    @classmethod
    def _no_prod(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("G-4 dry-run approval requires no_production_mutation_verified=True")
        return value


class DryRunApproval(FeiyueModel):
    """An exact approval record for a specific Hermes dry-run session draft."""

    approval_id: str
    draft_id: str
    approved_by: str
    reason: str
    status: str = "approved_dry_run"
    draft_status_before_approval: str = "blocked_until_exact_approval"
    draft_status_after_approval: str = "approved_dry_run"
    dry_run_only_verified: bool = True
    provider_call_budget_verified: int = 0
    no_hermes_start_verified: bool = True
    no_production_mutation_verified: bool = True
    no_global_config_mutation_verified: bool = True
    profile_verified: str = ""
    toolsets_verified: list[str] = Field(default_factory=list)
    approved_at: str
    events_path: str
    verifier_evidence_path: str
    next_required_gate: str = "exact_human_approval_before_real_hermes_session"


class DryRunApprovalSummary(FeiyueModel):
    """Summary of all dry-run approvals."""

    approvals: list[DryRunApproval] = Field(default_factory=list)
    dry_run_only: bool = True
    provider_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


class DryRunApprovalResult(FeiyueModel):
    """Result of creating a dry-run approval."""

    approval: DryRunApproval
    verifier_evidence: dict[str, object]
    approval_path: str
    verifier_evidence_path: str
    events: list[dict[str, object]]
    dry_run_only: bool = True
    provider_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


class DryRunApprovalError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def approval_gate_dir(project_root: str | Path) -> Path:
    return Path(project_root) / ".hermes" / "approval-gate"


def _safe_id(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in "-_" for ch in value)


def list_dry_run_approvals(project_root: str | Path) -> DryRunApprovalSummary:
    approvals = []
    for path in sorted(approval_gate_dir(project_root).glob("*/approval.json")):
        payload = _read_json_object(path)
        if payload:
            approvals.append(DryRunApproval.model_validate(payload))
    return DryRunApprovalSummary(approvals=approvals)


def read_dry_run_approval(project_root: str | Path, approval_id: str) -> DryRunApproval:
    if not _safe_id(approval_id):
        raise DryRunApprovalError("approval_id is not safe", status_code=400)
    path = approval_gate_dir(project_root) / approval_id / "approval.json"
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise DryRunApprovalError("Dry-run approval not found", status_code=404)
    payload = _read_json_object(path)
    if not payload:
        raise DryRunApprovalError("Dry-run approval record is invalid", status_code=500)
    return DryRunApproval.model_validate(payload)


def create_dry_run_approval(
    project_root: str | Path,
    request: DryRunApprovalRequest,
) -> DryRunApprovalResult:
    """Create an exact dry-run approval for a session draft.

    The approval is tied to the exact draft_id. It does NOT start Hermes,
    call providers, execute tools, or mutate production state.
    """
    root = Path(project_root)
    now = datetime.now(UTC).isoformat()

    # Validate draft exists
    draft_dir = root / ".hermes" / "hermes-session-drafts" / request.draft_id
    draft_path = draft_dir / "draft.json"
    if not draft_path.exists():
        raise DryRunApprovalError(
            f"Hermes session draft {request.draft_id} not found. Create the draft first.",
            status_code=404,
        )

    # Read current draft to verify exact match
    draft_payload = _read_json_object(draft_path)
    if not draft_payload:
        raise DryRunApprovalError("Cannot read Hermes session draft payload", status_code=500)

    if draft_payload.get("status") != "blocked_until_exact_approval":
        raise DryRunApprovalError(
            f"Draft {request.draft_id} has status '{draft_payload.get('status')}' and cannot be approved (expected 'blocked_until_exact_approval')",
            status_code=400,
        )

    approval_id = request.draft_id
    verifier_evidence_rel = f".hermes/approval-gate/{approval_id}/verifier-evidence.json"
    events_rel = f".hermes/approval-gate/{approval_id}/events.json"

    approval = DryRunApproval(
        approval_id=approval_id,
        draft_id=request.draft_id,
        approved_by=request.approved_by,
        reason=request.reason,
        approved_at=now,
        events_path=events_rel,
        verifier_evidence_path=verifier_evidence_rel,
        profile_verified=request.profile_verified or draft_payload.get("profile", ""),
        toolsets_verified=request.toolsets_verified or draft_payload.get("toolsets", []),
    )

    # Read the original events and append the approval event
    events_path = draft_dir / "events.json"
    original_events: list[dict[str, object]] = []
    if events_path.exists():
        raw = _read_json_object(events_path)
        if isinstance(raw, list):
            original_events = raw
    # In case events.json is a dict (weird read), treat as empty
    if not isinstance(original_events, list):
        original_events = []

    approved_events = list(original_events)
    next_seq = (approved_events[-1]["sequence"] + 1) if approved_events else 1
    approved_events.append({
        "sequence": next_seq,
        "event_type": "dry_run_approved",
        "message": f"Exact dry-run approval granted by {request.approved_by}: {request.reason}",
        "redacted": True,
        "provider_call_count": 0,
        "tool_call_count": 0,
        "created_at": now,
    })
    approved_events.append({
        "sequence": next_seq + 1,
        "event_type": "pending_real_hermes_start",
        "message": "Draft approved for dry-run execution. Real Hermes session still requires exact human approval.",
        "redacted": True,
        "provider_call_count": 0,
        "tool_call_count": 0,
        "created_at": now,
    })

    # Write approval artifacts
    gate_dir = approval_gate_dir(root) / approval_id
    gate_dir.mkdir(parents=True, exist_ok=True)

    (gate_dir / "approval.json").write_text(
        json.dumps(approval.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    (gate_dir / "events.json").write_text(
        json.dumps(approved_events, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # Update the draft status in place
    draft_payload["status"] = "approved_dry_run"
    draft_payload["approval_required"] = True
    draft_payload["next_required_gate"] = "exact_human_approval_before_real_hermes_session"
    draft_path.write_text(
        json.dumps(draft_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # Write verifier evidence
    verifier_evidence = {
        "approval_id": approval_id,
        "draft_id": request.draft_id,
        "approved_by": request.approved_by,
        "approved_at": now,
        "verification_checks": {
            "dry_run_only_verified": request.dry_run_only_verified,
            "provider_call_budget_verified": request.provider_call_budget_verified,
            "no_hermes_start_verified": request.no_hermes_start_verified,
            "no_production_mutation_verified": request.no_production_mutation_verified,
            "no_global_config_mutation_verified": request.no_global_config_mutation_verified,
        },
        "draft_status_before": "blocked_until_exact_approval",
        "draft_status_after": "approved_dry_run",
        "provider_call_count_after_approval": 0,
        "hermes_started_after_approval": False,
        "boundary_preserved": True,
        "next_required_gate": "exact_human_approval_before_real_hermes_session",
    }
    (gate_dir / "verifier-evidence.json").write_text(
        json.dumps(verifier_evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return DryRunApprovalResult(
        approval=approval,
        verifier_evidence=verifier_evidence,
        approval_path=(gate_dir / "approval.json").relative_to(root).as_posix(),
        verifier_evidence_path=(gate_dir / "verifier-evidence.json").relative_to(root).as_posix(),
        events=approved_events,
    )


def read_approval_events(project_root: str | Path, approval_id: str) -> list[dict[str, object]]:
    if not _safe_id(approval_id):
        raise DryRunApprovalError("approval_id is not safe", status_code=400)
    path = approval_gate_dir(project_root) / approval_id / "events.json"
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise DryRunApprovalError("Approval events not found", status_code=404)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise DryRunApprovalError("Approval events payload is invalid", status_code=500)
    return payload


def read_approval_verifier_evidence(project_root: str | Path, approval_id: str) -> dict[str, object]:
    if not _safe_id(approval_id):
        raise DryRunApprovalError("approval_id is not safe", status_code=400)
    path = approval_gate_dir(project_root) / approval_id / "verifier-evidence.json"
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise DryRunApprovalError("Verifier evidence not found", status_code=404)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DryRunApprovalError("Verifier evidence payload is invalid", status_code=500)
    return payload


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
