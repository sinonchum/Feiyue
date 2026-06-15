"""Provider-free Hermes session drafts for the Feiyue operator console.

G-3 introduces the shape of a Hermes Bridge session surface without starting
Hermes, calling providers, executing tools, or mutating production state. The
artifacts here are project-local dry-run drafts plus deterministic simulated
redacted events that a future approved Bridge sidecar can replace.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel

_ALLOWED_PROFILES = {"default", "local-qwen25-coder", "dry-run"}
_ALLOWED_TOOLSETS = {"none", "file", "terminal", "browser", "web"}


class HermesSessionDraftRequest(FeiyueModel):
    goal: str
    profile: str = "dry-run"
    created_by: str = "operator"
    reason: str = "operator_requested_hermes_session_draft"
    toolsets: list[str] = Field(default_factory=lambda: ["none"])
    dry_run_only: bool = True
    provider_call_budget: int = 0

    @field_validator("goal", "profile", "created_by", "reason")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field must be non-empty")
        return text

    @field_validator("profile")
    @classmethod
    def _allowlisted_profile(cls, value: str) -> str:
        if value not in _ALLOWED_PROFILES:
            raise ValueError("profile is not allowlisted for G-3 dry-run drafts")
        return value

    @field_validator("toolsets")
    @classmethod
    def _allowlisted_toolsets(cls, value: list[str]) -> list[str]:
        if not value:
            return ["none"]
        normalized = []
        for item in value:
            toolset = item.strip()
            if toolset not in _ALLOWED_TOOLSETS:
                raise ValueError("toolset is not allowlisted for G-3 dry-run drafts")
            normalized.append(toolset)
        return normalized

    @field_validator("dry_run_only")
    @classmethod
    def _must_be_dry_run(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("G-3 Hermes session drafts must be dry_run_only")
        return value

    @field_validator("provider_call_budget")
    @classmethod
    def _no_provider_budget(cls, value: int) -> int:
        if value != 0:
            raise ValueError("G-3 provider_call_budget must be 0")
        return value


class HermesSessionEvent(FeiyueModel):
    sequence: int
    event_type: str
    message: str
    redacted: bool = True
    provider_call_count: int = 0
    tool_call_count: int = 0
    created_at: str


class HermesSessionDraft(FeiyueModel):
    draft_id: str
    status: str = "blocked_until_exact_approval"
    goal_hash: str
    profile: str
    created_by: str
    reason: str
    toolsets: list[str]
    dry_run_only: bool = True
    provider_call_budget: int = 0
    provider_call_count: int = 0
    tool_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    approval_required: bool = True
    next_required_gate: str = "exact_human_approval_before_real_hermes_session"
    created_at: str
    events_path: str


class HermesSessionDraftSummary(FeiyueModel):
    drafts: list[HermesSessionDraft] = Field(default_factory=list)
    dry_run_only: bool = True
    provider_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


class HermesSessionDraftResult(FeiyueModel):
    draft: HermesSessionDraft
    events: list[HermesSessionEvent]
    draft_path: str
    events_path: str
    dry_run_only: bool = True
    provider_call_count: int = 0
    hermes_started: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


class HermesSessionDraftError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def hermes_session_drafts_dir(project_root: str | Path) -> Path:
    return Path(project_root) / ".hermes" / "hermes-session-drafts"


def list_hermes_session_drafts(project_root: str | Path) -> HermesSessionDraftSummary:
    drafts = []
    for path in sorted(hermes_session_drafts_dir(project_root).glob("*/draft.json")):
        payload = _read_json_object(path)
        if payload:
            drafts.append(HermesSessionDraft.model_validate(payload))
    return HermesSessionDraftSummary(drafts=drafts)


def read_hermes_session_events(project_root: str | Path, draft_id: str) -> list[HermesSessionEvent]:
    if not _safe_id(draft_id):
        raise HermesSessionDraftError("draft_id is not safe", status_code=400)
    path = hermes_session_drafts_dir(project_root) / draft_id / "events.json"
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise HermesSessionDraftError("Hermes session draft events not found", status_code=404)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise HermesSessionDraftError("Hermes session events payload is invalid", status_code=500)
    return [HermesSessionEvent.model_validate(item) for item in payload]


def create_hermes_session_draft(project_root: str | Path, request: HermesSessionDraftRequest) -> HermesSessionDraftResult:
    root = Path(project_root)
    now = datetime.now(UTC).isoformat()
    draft_id = _draft_id(request, now)
    events_rel = f".hermes/hermes-session-drafts/{draft_id}/events.json"
    draft = HermesSessionDraft(
        draft_id=draft_id,
        goal_hash=hashlib.sha256(request.goal.encode("utf-8")).hexdigest(),
        profile=request.profile,
        created_by=request.created_by,
        reason=request.reason,
        toolsets=request.toolsets,
        created_at=now,
        events_path=events_rel,
    )
    events = _simulated_events(draft, now)
    draft_path = hermes_session_drafts_dir(root) / draft_id / "draft.json"
    events_path = hermes_session_drafts_dir(root) / draft_id / "events.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(json.dumps(draft.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    events_path.write_text(
        json.dumps([event.model_dump(mode="json") for event in events], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return HermesSessionDraftResult(
        draft=draft,
        events=events,
        draft_path=draft_path.relative_to(root).as_posix(),
        events_path=events_path.relative_to(root).as_posix(),
    )


def _simulated_events(draft: HermesSessionDraft, now: str) -> list[HermesSessionEvent]:
    return [
        HermesSessionEvent(
            sequence=1,
            event_type="session_draft_created",
            message="Provider-free Hermes Bridge dry-run draft created; no Hermes process started.",
            created_at=now,
        ),
        HermesSessionEvent(
            sequence=2,
            event_type="policy_checked",
            message="Profile, toolsets, dry_run_only, and provider_call_budget passed G-3 guard checks.",
            created_at=now,
        ),
        HermesSessionEvent(
            sequence=3,
            event_type="approval_required",
            message="Exact human approval is required before a real Hermes Bridge session may start.",
            created_at=now,
        ),
        HermesSessionEvent(
            sequence=4,
            event_type="blocked_until_exact_approval",
            message=f"Draft {draft.draft_id} remains blocked; provider_call_count=0 and tool_call_count=0.",
            created_at=now,
        ),
    ]


def _draft_id(request: HermesSessionDraftRequest, now: str) -> str:
    seed = json.dumps(
        {
            "goal": request.goal,
            "profile": request.profile,
            "created_by": request.created_by,
            "reason": request.reason,
            "toolsets": request.toolsets,
            "created_at": now,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"hermes-dryrun-{digest}"


def _safe_id(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in "-_" for ch in value)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
