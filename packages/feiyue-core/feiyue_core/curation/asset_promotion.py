"""Provider-free persistence for reviewed asset promotion proposals.

This module writes only to a caller-supplied project/profile root under
``.hermes/asset-proposals``. Promotion creates a safe audit artifact inside the
proposal directory; it never installs skills, evals, templates, or other formal
Hermes assets.
"""

from __future__ import annotations

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

    def promote(self, proposal_id: str, *, reviewer: str, reason: str, decided_at: str) -> AssetReviewDecision:
        """Promote an approved proposal to a safe artifact in its proposal directory."""

        record = self.load_proposal(proposal_id)
        if record.status is AssetProposalStatus.REJECTED:
            raise PromotionBlockedError(f"proposal {proposal_id} is rejected and cannot be promoted")
        if record.status is not AssetProposalStatus.APPROVED:
            raise PromotionBlockedError(f"proposal {proposal_id} is not approved and cannot be promoted")

        decision = AssetReviewDecision(
            proposal_id=proposal_id,
            decision="promote",
            reviewer=reviewer,
            reason=reason,
            decided_at=decided_at,
        )
        self._append_decision(decision)
        (self._proposal_dir(proposal_id) / "promotion.json").write_text(
            decision.model_dump_json(indent=2) + "\n",
        )
        self._write_record(record.model_copy(update={"status": AssetProposalStatus.PROMOTED}))
        return decision

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
