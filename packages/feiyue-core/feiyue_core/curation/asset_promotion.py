"""Provider-free persistence and sandboxed promotion for reviewed asset proposals.

This module writes only to a caller-supplied project/profile root. Proposal
records live under ``.hermes/asset-proposals``. Approved promotion may write
formal assets only inside that same project-local ``.hermes`` sandbox and only
under explicit allowlisted asset roots.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from feiyue_core.curation.distillation_proposal import DistillationProposal, ProposalStatus
from feiyue_core.schemas.common import FeiyueModel


class AssetPromotionError(RuntimeError):
    """Raised when asset proposal persistence cannot proceed safely."""


class PromotionBlockedError(AssetPromotionError):
    """Raised when a proposal status fails the promotion gate."""


class AssetProposalStatus(StrEnum):
    """Persisted lifecycle for provider-free asset proposals."""

    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTED = "promoted"


DecisionKind = Literal["approve", "reject", "promote"]

_ASSET_TYPE_DEFAULT_DIRS: dict[str, str] = {
    "lesson": "lessons",
    "regression_eval": "evals",
    "task_template": "task-templates",
    "skill": "assets/skill",
    "project_memory": "assets/project_memory",
    "routing_rule": "assets/routing_rule",
}

_ALLOWLIST_ROOTS = (
    ".hermes/assets",
    ".hermes/lessons",
    ".hermes/evals",
    ".hermes/task-templates",
)

ReasonCode = Literal[
    "approval_missing",
    "proposal_rejected",
    "target_path_not_allowed",
    "duplicate_content_hash",
    "rollback_ref_missing",
    "patch_missing",
]


class AssetReviewDecision(FeiyueModel):
    """Append-only review or promotion decision record."""

    proposal_id: str
    decision: DecisionKind
    reviewer: str
    reason: str
    decided_at: str

    @field_validator("proposal_id", "reviewer", "reason", "decided_at")
    @classmethod
    def fields_must_not_be_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("decision fields must not be empty")
        return value


class AssetProposalRecord(FeiyueModel):
    """On-disk proposal record including provenance and current status."""

    proposal_id: str
    status: AssetProposalStatus
    provenance: dict[str, Any] = Field(default_factory=dict)
    proposal: dict[str, Any]

    @field_validator("proposal_id")
    @classmethod
    def proposal_id_must_not_be_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("proposal_id must not be empty")
        return value


class PromotionEvidence(FeiyueModel):
    """Durable evidence for an attempted sandboxed asset promotion."""

    proposal_id: str
    patch_id: str | None = None
    patch_index: int | None = None
    target_path: str
    content_hash: str
    rollback_snapshot: dict[str, Any]
    promoted: bool
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    reviewer: str
    reason: str
    decided_at: str

    @field_validator("proposal_id", "reviewer", "reason", "decided_at")
    @classmethod
    def required_text_fields_must_not_be_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("promotion evidence fields must not be empty")
        return value


_SECRET_KEYS = ("password", "secret", "token", "api_key", "apikey", "credential")


def _redact_secret_like_values(value: Any, *, key: str = "") -> Any:
    """Redact secret-like metadata by key name while preserving shape."""

    if any(secret_key in key.lower() for secret_key in _SECRET_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(child_key): _redact_secret_like_values(child_value, key=str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [_redact_secret_like_values(item) for item in value]
    return value


class AssetPromotionStore:
    """Persist asset proposals and append review decisions under a safe root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.proposals_root = self.root / ".hermes" / "asset-proposals"

    def persist_proposal(
        self,
        proposal: DistillationProposal | FeiyueModel | dict[str, Any],
        *,
        provenance: dict[str, Any] | None = None,
    ) -> AssetProposalRecord:
        """Write ``proposal.json`` for a proposal-like object and return its record."""

        proposal_data = self._proposal_to_dict(proposal)
        proposal_id = self._require_text(proposal_data.get("proposal_id"), "proposal_id")
        status = self._coerce_status(proposal_data.get("status", AssetProposalStatus.REVIEW_REQUIRED.value))
        merged_provenance = self._extract_provenance(proposal_data)
        if provenance is not None:
            merged_provenance.update(provenance)
        record = AssetProposalRecord(
            proposal_id=proposal_id,
            status=status,
            provenance=_redact_secret_like_values(merged_provenance),
            proposal=_redact_secret_like_values(proposal_data),
        )
        self._write_record(record)
        return record

    def load_proposal(self, proposal_id: str) -> AssetProposalRecord:
        """Load a persisted proposal record, failing closed if it is missing."""

        path = self._proposal_path(proposal_id)
        if not path.exists():
            raise AssetPromotionError(f"missing proposal: {proposal_id}")
        return AssetProposalRecord.model_validate_json(path.read_text())

    def approve(self, proposal_id: str, *, reviewer: str, reason: str, decided_at: str) -> AssetReviewDecision:
        """Append an approval decision and set status to approved."""

        return self._append_decision_and_update_status(
            proposal_id,
            decision="approve",
            reviewer=reviewer,
            reason=reason,
            decided_at=decided_at,
            new_status=AssetProposalStatus.APPROVED,
        )

    def reject(self, proposal_id: str, *, reviewer: str, reason: str, decided_at: str) -> AssetReviewDecision:
        """Append a rejection decision and set status to rejected."""

        return self._append_decision_and_update_status(
            proposal_id,
            decision="reject",
            reviewer=reviewer,
            reason=reason,
            decided_at=decided_at,
            new_status=AssetProposalStatus.REJECTED,
        )

    def promote(
        self,
        proposal_id: str,
        *,
        reviewer: str,
        reason: str,
        decided_at: str,
        rollback_ref: str | None = None,
        patch_id: str | None = None,
        patch_index: int = 0,
    ) -> PromotionEvidence:
        """Promote one approved proposal patch into project-local ``.hermes`` assets.

        The method fails closed: any missing approval, rejected status, unsafe
        target path, duplicate content hash, or missing rollback reference
        produces non-promoted evidence and leaves asset files untouched.
        """

        record = self.load_proposal(proposal_id)
        patch_index_resolved, patch = self._proposal_patch(record, patch_index=patch_index, patch_id=patch_id)
        content = str(patch.get("proposed_content", "")) if patch is not None else ""
        content_hash = self._content_hash(content)
        target_path = self._target_path_for_patch(record, patch) if patch is not None else ""
        target_allowed = self._is_allowed_target_path(target_path)
        rollback_snapshot = self._rollback_snapshot(target_path, rollback_ref) if target_allowed else {
            "rollback_ref": rollback_ref,
            "existed": False,
        }
        reason_codes: list[ReasonCode] = []

        if record.status is AssetProposalStatus.REJECTED:
            reason_codes.append("proposal_rejected")
        elif record.status is not AssetProposalStatus.APPROVED:
            reason_codes.append("approval_missing")
        if not rollback_ref:
            reason_codes.append("rollback_ref_missing")
        if patch is None:
            reason_codes.append("patch_missing")
        elif not target_allowed:
            reason_codes.append("target_path_not_allowed")
        elif self._duplicate_content_hash_exists(content_hash, target_path):
            reason_codes.append("duplicate_content_hash")

        promoted = not reason_codes
        evidence = PromotionEvidence(
            proposal_id=proposal_id,
            patch_id=self._patch_id_for_evidence(patch_index_resolved, patch, patch_id),
            patch_index=patch_index_resolved,
            target_path=target_path,
            content_hash=content_hash,
            rollback_snapshot=rollback_snapshot,
            promoted=promoted,
            reason_codes=reason_codes,
            reviewer=reviewer,
            reason=reason,
            decided_at=decided_at,
        )
        self._write_promotion_evidence(evidence)

        decision = AssetReviewDecision(
            proposal_id=proposal_id,
            decision="promote",
            reviewer=reviewer,
            reason=reason,
            decided_at=decided_at,
        )
        self._append_decision(decision)

        if not promoted:
            return evidence

        target = self.root / target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        next_status = AssetProposalStatus.PROMOTED if self._all_patches_promoted(record, patch_index_resolved) else AssetProposalStatus.APPROVED
        self._write_record(record.model_copy(update={"status": next_status}))
        self._write_promotion_evidence(evidence)
        return evidence

    def simulate_rollback(self, evidence: PromotionEvidence | dict[str, Any]) -> dict[str, Any]:
        """Apply the rollback snapshot from promotion evidence in the sandbox."""

        evidence_model = evidence if isinstance(evidence, PromotionEvidence) else PromotionEvidence.model_validate(evidence)
        if not self._is_allowed_target_path(evidence_model.target_path):
            return {"rolled_back": False, "reason_codes": ["target_path_not_allowed"]}
        target = self.root / evidence_model.target_path
        snapshot = evidence_model.rollback_snapshot
        if snapshot.get("existed"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(snapshot.get("content", "")))
        elif target.exists():
            target.unlink()
        return {"rolled_back": True, "target_path": evidence_model.target_path}

    def _proposal_patch(
        self,
        record: AssetProposalRecord,
        *,
        patch_index: int,
        patch_id: str | None,
    ) -> tuple[int | None, dict[str, Any] | None]:
        patches = record.proposal.get("patches", [])
        if not isinstance(patches, list):
            return None, None
        if patch_id is not None:
            for index, patch in enumerate(patches):
                if isinstance(patch, dict) and self._patch_selection_id(index, patch) == patch_id:
                    return index, patch
            return None, None
        if patch_index < 0 or patch_index >= len(patches):
            return None, None
        patch = patches[patch_index]
        return (patch_index, patch) if isinstance(patch, dict) else (None, None)

    def _patch_selection_id(self, patch_index: int, patch: dict[str, Any]) -> str:
        raw_patch_id = patch.get("patch_id") or patch.get("id")
        if isinstance(raw_patch_id, str) and raw_patch_id:
            return raw_patch_id
        asset_type = patch.get("asset_type")
        if isinstance(asset_type, str) and asset_type:
            return asset_type
        return f"patch-{patch_index}"

    def _patch_id_for_evidence(self, patch_index: int | None, patch: dict[str, Any] | None, requested_patch_id: str | None) -> str | None:
        if patch is not None and patch_index is not None:
            return self._patch_selection_id(patch_index, patch)
        return requested_patch_id

    def _all_patches_promoted(self, record: AssetProposalRecord, current_patch_index: int | None) -> bool:
        patches = record.proposal.get("patches", [])
        if not isinstance(patches, list) or current_patch_index is None:
            return False
        promoted_indexes = {current_patch_index}
        promotions_dir = self._proposal_dir(record.proposal_id) / "promotions"
        if promotions_dir.exists():
            for path in promotions_dir.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if payload.get("promoted") is True and isinstance(payload.get("patch_index"), int):
                    promoted_indexes.add(int(payload["patch_index"]))
        return len(promoted_indexes) >= len(patches)

    def _target_path_for_patch(self, record: AssetProposalRecord, patch: dict[str, Any]) -> str:
        raw_target = patch.get("target_path")
        if isinstance(raw_target, str) and raw_target:
            normalized = raw_target.replace("\\", "/").lstrip("/")
            if normalized.startswith(".hermes/"):
                return normalized
            return f".hermes/{normalized}"
        asset_type = str(patch.get("asset_type", ""))
        default_dir = _ASSET_TYPE_DEFAULT_DIRS.get(asset_type, f"assets/{asset_type}")
        return f".hermes/{default_dir}/{record.proposal_id}.md"

    def _is_allowed_target_path(self, target_path: str) -> bool:
        if not target_path:
            return False
        candidate = (self.root / target_path).resolve()
        sandbox = (self.root / ".hermes").resolve()
        try:
            candidate.relative_to(sandbox)
        except ValueError:
            return False
        normalized = candidate.relative_to(self.root.resolve()).as_posix()
        return any(normalized == root or normalized.startswith(f"{root}/") for root in _ALLOWLIST_ROOTS)

    def _rollback_snapshot(self, target_path: str, rollback_ref: str | None) -> dict[str, Any]:
        target = self.root / target_path
        if target.exists():
            content = target.read_text()
            return {
                "rollback_ref": rollback_ref,
                "existed": True,
                "content": content,
                "content_hash": self._content_hash(content),
            }
        return {"rollback_ref": rollback_ref, "existed": False}

    def _duplicate_content_hash_exists(self, content_hash: str, target_path: str) -> bool:
        hermes = self.root / ".hermes"
        if not hermes.exists():
            return False
        target = (self.root / target_path).resolve()
        for allow_root in _ALLOWLIST_ROOTS:
            root = self.root / allow_root
            if not root.exists():
                continue
            for existing in root.rglob("*"):
                if not existing.is_file() or existing.resolve() == target:
                    continue
                try:
                    if self._content_hash(existing.read_text()) == content_hash:
                        return True
                except UnicodeDecodeError:
                    continue
        return False

    def _write_promotion_evidence(self, evidence: PromotionEvidence) -> None:
        proposal_dir = self._proposal_dir(evidence.proposal_id)
        path = proposal_dir / "promotions" / f"{self._promotion_evidence_name(evidence)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = evidence.model_dump_json(indent=2) + "\n"
        path.write_text(payload)
        (proposal_dir / "promotion.json").write_text(payload)

    def _promotion_evidence_name(self, evidence: PromotionEvidence) -> str:
        name = evidence.patch_id or (f"patch-{evidence.patch_index}" if evidence.patch_index is not None else "unknown-patch")
        safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in name)
        return safe.strip(".-") or "unknown-patch"

    def _content_hash(self, content: str) -> str:
        return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _append_decision_and_update_status(
        self,
        proposal_id: str,
        *,
        decision: DecisionKind,
        reviewer: str,
        reason: str,
        decided_at: str,
        new_status: AssetProposalStatus,
    ) -> AssetReviewDecision:
        record = self.load_proposal(proposal_id)
        decision_record = AssetReviewDecision(
            proposal_id=proposal_id,
            decision=decision,
            reviewer=reviewer,
            reason=reason,
            decided_at=decided_at,
        )
        self._append_decision(decision_record)
        self._write_record(record.model_copy(update={"status": new_status}))
        return decision_record

    def _append_decision(self, decision: AssetReviewDecision) -> None:
        path = self._proposal_dir(decision.proposal_id) / "decisions.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(decision.model_dump_json() + "\n")

    def _write_record(self, record: AssetProposalRecord) -> None:
        path = self._proposal_path(record.proposal_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.model_dump_json(indent=2) + "\n")

    def _proposal_dir(self, proposal_id: str) -> Path:
        if not proposal_id or "/" in proposal_id or "\\" in proposal_id or proposal_id in {".", ".."}:
            raise AssetPromotionError(f"unsafe proposal_id: {proposal_id!r}")
        return self.proposals_root / proposal_id

    def _proposal_path(self, proposal_id: str) -> Path:
        return self._proposal_dir(proposal_id) / "proposal.json"

    def _proposal_to_dict(self, proposal: DistillationProposal | FeiyueModel | dict[str, Any]) -> dict[str, Any]:
        if isinstance(proposal, dict):
            return dict(proposal)
        if isinstance(proposal, FeiyueModel):
            return proposal.model_dump(mode="json")
        raise TypeError("proposal must be a FeiyueModel or dict")

    def _coerce_status(self, status: Any) -> AssetProposalStatus:
        if isinstance(status, AssetProposalStatus):
            return status
        if isinstance(status, ProposalStatus):
            return AssetProposalStatus(status.value)
        try:
            return AssetProposalStatus(str(status))
        except ValueError as exc:
            raise AssetPromotionError(f"unsupported proposal status: {status!r}") from exc

    def _extract_provenance(self, proposal_data: dict[str, Any]) -> dict[str, Any]:
        provenance: dict[str, Any] = {}
        for key in (
            "source_task_id",
            "source_input_id",
            "source_trace_refs",
            "source_trace_ids",
            "verifier_refs",
            "teacher_refs",
        ):
            if key in proposal_data and proposal_data[key] is not None:
                provenance[key] = proposal_data[key]
        source_ids: list[str] = []
        for patch in proposal_data.get("patches", []):
            if isinstance(patch, dict):
                source_ids.extend(str(source_id) for source_id in patch.get("source_ids", []) if source_id)
        if source_ids:
            provenance["source_ids"] = list(dict.fromkeys(source_ids))
        return provenance

    def _require_text(self, value: Any, field_name: str) -> str:
        if not isinstance(value, str) or value == "":
            raise AssetPromotionError(f"missing proposal {field_name}")
        return value
