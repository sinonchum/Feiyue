"""Provider-free review gate decisions for distillation proposals."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from feiyue_core.curation.distillation_proposal import (
    DistillationProposal,
    ProposalStatus,
)
from feiyue_core.schemas.common import FeiyueModel


class InvalidReviewTransitionError(ValueError):
    """Raised when a proposal status cannot enter the review gate."""


class ReviewDecisionStatus(StrEnum):
    """Allowed review outcomes for a distillation proposal."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReviewDecision(FeiyueModel):
    """A provider-free human review decision for a distillation proposal."""

    decision_id: str
    proposal_id: str
    decision: ReviewDecisionStatus
    reviewer_id: str
    rationale: str
    source_ids: list[str] = Field(min_length=1)

    @field_validator("reviewer_id")
    @classmethod
    def reviewer_id_must_not_be_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("reviewer_id must not be empty")
        return value

    @field_validator("rationale")
    @classmethod
    def rationale_must_not_be_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("rationale must not be empty")
        return value

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_not_contain_empty_values(cls, value: list[str]) -> list[str]:
        if any(source_id == "" for source_id in value):
            raise ValueError("source_ids must not contain empty values")
        return value

    def render_markdown(self) -> str:
        """Render this decision as deterministic Markdown for human audit."""

        source_ids = "".join(f"- {source_id}\n" for source_id in self.source_ids)
        return (
            f"# Review Decision: {self.decision_id}\n\n"
            "## Proposal\n\n"
            f"{self.proposal_id}\n\n"
            "## Decision\n\n"
            f"{self.decision.value}\n\n"
            "## Reviewer\n\n"
            f"{self.reviewer_id}\n\n"
            "## Rationale\n\n"
            f"{self.rationale}\n\n"
            "## Source IDs\n\n"
            f"{source_ids}"
        )


class ReviewGate:
    """Create review decisions without applying proposal side effects."""

    _REVIEWABLE_STATUSES = {
        ProposalStatus.REVIEW_REQUIRED.value,
        ProposalStatus.DRAFT.value,
    }

    def accept(
        self,
        proposal: DistillationProposal,
        decision_id: str,
        reviewer_id: str,
        rationale: str,
        source_ids: list[str] | None = None,
    ) -> ReviewDecision:
        """Accept a reviewable proposal."""

        return self._decide(
            proposal=proposal,
            decision_id=decision_id,
            decision=ReviewDecisionStatus.ACCEPTED,
            reviewer_id=reviewer_id,
            rationale=rationale,
            source_ids=source_ids,
        )

    def reject(
        self,
        proposal: DistillationProposal,
        decision_id: str,
        reviewer_id: str,
        rationale: str,
        source_ids: list[str] | None = None,
    ) -> ReviewDecision:
        """Reject a reviewable proposal."""

        return self._decide(
            proposal=proposal,
            decision_id=decision_id,
            decision=ReviewDecisionStatus.REJECTED,
            reviewer_id=reviewer_id,
            rationale=rationale,
            source_ids=source_ids,
        )

    def _decide(
        self,
        *,
        proposal: DistillationProposal,
        decision_id: str,
        decision: ReviewDecisionStatus,
        reviewer_id: str,
        rationale: str,
        source_ids: list[str] | None,
    ) -> ReviewDecision:
        self._ensure_reviewable(proposal)
        return ReviewDecision(
            decision_id=decision_id,
            proposal_id=proposal.proposal_id,
            decision=decision,
            reviewer_id=reviewer_id,
            rationale=rationale,
            source_ids=source_ids if source_ids is not None else self._default_source_ids(proposal),
        )

    def _ensure_reviewable(self, proposal: DistillationProposal) -> None:
        status = proposal.status.value if isinstance(proposal.status, ProposalStatus) else proposal.status
        if status not in self._REVIEWABLE_STATUSES:
            raise InvalidReviewTransitionError(
                f"proposal {proposal.proposal_id} with status {status!r} cannot be reviewed"
            )

    def _default_source_ids(self, proposal: DistillationProposal) -> list[str]:
        return [proposal.proposal_id, proposal.source_input_id, proposal.source_task_id]
