"""Draft-only review intents for the Feiyue operator console.

G-2 intent drafts are intentionally narrower than approvals: they capture an
operator intent to review/create an approval candidate later, but they never
apply routing, start Hermes, call providers, promote code, or mutate global
Hermes configuration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.review_inbox import ReviewInbox


INTENT_KIND_BY_RECOMMENDED_ACTION = {
    "review_and_create_routing_proposal_approval": "routing_approval_draft",
    "apply_approved_routing_proposal": "routing_apply_review_draft",
    "review_and_create_promotion_approval": "promotion_review_draft",
    "review_and_create_draft_pr_approval": "draft_pr_review_draft",
    "review_and_create_multi_worker_dry_run_approval": "multi_worker_review_draft",
    "review_asset_proposal": "asset_review_draft",
}


class ReviewIntentDraftRequest(FeiyueModel):
    item_type: str
    item_id: str
    recommended_action: str
    evidence_path: str
    created_by: str = "operator"
    reason: str = "operator_requested_intent_draft"

    @field_validator("item_type", "item_id", "recommended_action", "evidence_path", "created_by", "reason")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field must be non-empty")
        return text

    @field_validator("evidence_path")
    @classmethod
    def _relative_hermes_path(cls, value: str) -> str:
        if value.startswith("/") or ":" in value or ".." in Path(value).parts:
            raise ValueError("evidence_path must be a safe project-relative path")
        if not value.startswith(".hermes/"):
            raise ValueError("evidence_path must point under .hermes/")
        return value


class ReviewIntentDraft(FeiyueModel):
    intent_id: str
    intent_kind: str
    item_type: str
    item_id: str
    recommended_action: str
    evidence_path: str
    created_by: str
    reason: str
    status: str = "drafted"
    next_required_gate: str = "human_review_then_exact_approval"
    draft_only: bool = True
    mutates_state: bool = False
    provider_call_count: int = 0
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    writes_approval: bool = False
    applies_routing: bool = False
    starts_hermes_session: bool = False
    created_at: str


class ReviewIntentDraftSummary(FeiyueModel):
    drafts: list[ReviewIntentDraft] = Field(default_factory=list)
    mutates_state: bool = False
    write_endpoints_added: int = 1
    provider_call_count: int = 0
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


class ReviewIntentDraftResult(FeiyueModel):
    draft: ReviewIntentDraft
    path: str
    draft_only: bool = True
    mutates_state: bool = True
    mutation_scope: str = "project_local_review_intent_draft_only"
    provider_call_count: int = 0
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False


class ReviewIntentDraftError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def review_intent_drafts_dir(project_root: str | Path) -> Path:
    return Path(project_root) / ".hermes" / "review-intent-drafts"


def list_review_intent_drafts(project_root: str | Path) -> ReviewIntentDraftSummary:
    drafts = []
    for path in sorted(review_intent_drafts_dir(project_root).glob("*/intent.json")):
        payload = _read_json_object(path)
        if payload:
            drafts.append(ReviewIntentDraft.model_validate(payload))
    return ReviewIntentDraftSummary(drafts=drafts)


def create_review_intent_draft(project_root: str | Path, request: ReviewIntentDraftRequest) -> ReviewIntentDraftResult:
    root = Path(project_root)
    item = _find_matching_inbox_item(root, request)
    if item is None:
        raise ReviewIntentDraftError("review inbox item does not exist or does not match the requested action", status_code=404)

    intent_kind = INTENT_KIND_BY_RECOMMENDED_ACTION.get(request.recommended_action, "review_intent_draft")
    now = datetime.now(UTC).isoformat()
    intent_id = _intent_id(request, now)
    draft = ReviewIntentDraft(
        intent_id=intent_id,
        intent_kind=intent_kind,
        item_type=request.item_type,
        item_id=request.item_id,
        recommended_action=request.recommended_action,
        evidence_path=request.evidence_path,
        created_by=request.created_by,
        reason=request.reason,
        created_at=now,
    )
    path = review_intent_drafts_dir(root) / intent_id / "intent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    return ReviewIntentDraftResult(draft=draft, path=path.relative_to(root).as_posix())


def _find_matching_inbox_item(project_root: Path, request: ReviewIntentDraftRequest):
    for item in ReviewInbox(project_root).summary().items:
        if (
            item.item_type == request.item_type
            and item.item_id == request.item_id
            and item.recommended_action == request.recommended_action
            and item.evidence_path == request.evidence_path
        ):
            return item
    return None


def _intent_id(request: ReviewIntentDraftRequest, now: str) -> str:
    seed = json.dumps(
        {
            "item_type": request.item_type,
            "item_id": request.item_id,
            "recommended_action": request.recommended_action,
            "evidence_path": request.evidence_path,
            "created_by": request.created_by,
            "reason": request.reason,
            "created_at": now,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    safe_item_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in request.item_id)[:48]
    return f"{request.item_type}-{safe_item_id}-{digest}"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
