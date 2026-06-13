"""Read-only review inbox for project-local Feiyue approval evidence.

The inbox only scans existing `.hermes/` files and reports items that appear to
be waiting for human review, approval, apply/run, or blocked follow-up. It never
creates approval records, applies routing changes, runs providers, or promotes
artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class ReviewInboxItem(FeiyueModel):
    item_type: str
    item_id: str
    status: str
    evidence_path: str
    recommended_action: str
    mutates_state: bool = False


class ReviewInboxSummary(FeiyueModel):
    items: list[ReviewInboxItem] = Field(default_factory=list)
    mutates_state: bool = False


class ReviewInbox:
    """Aggregate pending local review items without mutating project state."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.hermes_dir = self.project_root / ".hermes"

    def summary(self) -> ReviewInboxSummary:
        items = [
            *self._routing_proposals(),
            *self._workflow_promotions(),
            *self._multi_worker_plans(),
            *self._asset_proposals(),
        ]
        items.sort(key=lambda item: (item.item_type, item.item_id, item.status, item.evidence_path))
        return ReviewInboxSummary(items=items, mutates_state=False)

    def _routing_proposals(self) -> list[ReviewInboxItem]:
        root = self.hermes_dir / "routing-proposals"
        items: list[ReviewInboxItem] = []
        for proposal_path in _sorted_glob(root, "*/proposal.json"):
            payload = _read_json_object(proposal_path)
            proposal_id = _text(payload.get("proposal_id")) or proposal_path.parent.name
            approval_path = proposal_path.parent / "approval.json"
            apply_path = proposal_path.parent / "apply-evidence.json"
            apply_payload = _read_json_object(apply_path)
            apply_status = _text(apply_payload.get("status"))
            if apply_status == "applied":
                continue
            if not approval_path.exists():
                status = "pending_approval"
                action = "review_and_create_routing_proposal_approval"
                evidence_path = proposal_path
            elif not apply_path.exists():
                status = "pending_apply"
                action = "apply_approved_routing_proposal"
                evidence_path = approval_path
            else:
                status = f"apply_{apply_status}" if apply_status else "apply_needs_review"
                action = "review_routing_apply_evidence"
                evidence_path = apply_path
            items.append(_item("routing_proposal", proposal_id, status, evidence_path, action, self.project_root))
        return items

    def _workflow_promotions(self) -> list[ReviewInboxItem]:
        root = self.hermes_dir / "workflow-smokes"
        items: list[ReviewInboxItem] = []
        for evidence_path in _sorted_glob(root, "*/evidence.json"):
            payload = _read_json_object(evidence_path)
            run_id = _text(payload.get("run_id")) or evidence_path.parent.name
            status = _text(payload.get("status"))
            if status != "verified" or payload.get("dry_run_only") is False or payload.get("promotion_attempted") is True:
                continue
            promotion_dir = self.hermes_dir / "workflow-promotions" / run_id
            approval_path = promotion_dir / "approval.json"
            promotion_path = promotion_dir / "promotion-evidence.json"
            promotion_payload = _read_json_object(promotion_path)
            promotion_status = _text(promotion_payload.get("status"))
            if promotion_status == "promoted":
                continue
            if promotion_status == "blocked":
                items.append(
                    _item(
                        "workflow_promotion",
                        run_id,
                        "blocked_promotion",
                        promotion_path,
                        "review_blocked_promotion_evidence",
                        self.project_root,
                    )
                )
            elif not approval_path.exists():
                items.append(
                    _item(
                        "workflow_promotion",
                        run_id,
                        "pending_approval",
                        evidence_path,
                        "review_and_create_promotion_approval",
                        self.project_root,
                    )
                )
            elif not promotion_path.exists():
                items.append(
                    _item(
                        "workflow_promotion",
                        run_id,
                        "pending_promotion",
                        approval_path,
                        "promote_approved_dry_run",
                        self.project_root,
                    )
                )
        return items

    def _multi_worker_plans(self) -> list[ReviewInboxItem]:
        root = self.hermes_dir / "multi-worker-plans"
        items: list[ReviewInboxItem] = []
        run_plan_ids = self._multi_worker_workflow_plan_ids()
        for plan_path in _sorted_glob(root, "*/plan.json"):
            payload = _read_json_object(plan_path)
            plan_id = _text(payload.get("plan_id")) or plan_path.parent.name
            approval_path = plan_path.parent / "approval.json"
            if not approval_path.exists():
                items.append(
                    _item(
                        "multi_worker_plan",
                        plan_id,
                        "pending_approval",
                        plan_path,
                        "review_and_create_multi_worker_dry_run_approval",
                        self.project_root,
                    )
                )
            elif plan_id not in run_plan_ids:
                items.append(
                    _item(
                        "multi_worker_plan",
                        plan_id,
                        "pending_run",
                        approval_path,
                        "run_approved_multi_worker_dry_run",
                        self.project_root,
                    )
                )
        return items

    def _multi_worker_workflow_plan_ids(self) -> set[str]:
        root = self.hermes_dir / "multi-worker-workflows"
        plan_ids: set[str] = set()
        for evidence_path in _sorted_glob(root, "*/evidence.json"):
            payload = _read_json_object(evidence_path)
            plan_id = _text(payload.get("plan_id"))
            if plan_id:
                plan_ids.add(plan_id)
        return plan_ids

    def _asset_proposals(self) -> list[ReviewInboxItem]:
        root = self.hermes_dir / "asset-proposals"
        items: list[ReviewInboxItem] = []
        for proposal_path in _sorted_glob(root, "*/proposal.json"):
            payload = _read_json_object(proposal_path)
            proposal_id = _text(payload.get("proposal_id")) or proposal_path.parent.name
            status = _text(payload.get("status"))
            if status != "review_required":
                continue
            items.append(
                _item(
                    "asset_proposal",
                    proposal_id,
                    "review_required",
                    proposal_path,
                    "review_asset_proposal",
                    self.project_root,
                )
            )
        return items


def _item(item_type: str, item_id: str, status: str, evidence_path: Path, recommended_action: str, project_root: Path) -> ReviewInboxItem:
    return ReviewInboxItem(
        item_type=item_type,
        item_id=item_id,
        status=status,
        evidence_path=_relative(evidence_path, project_root),
        recommended_action=recommended_action,
        mutates_state=False,
    )


def _sorted_glob(root: Path, pattern: str) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted((path for path in root.glob(pattern) if path.is_file() and not path.is_symlink()), key=lambda path: path.as_posix())


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _relative(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()
