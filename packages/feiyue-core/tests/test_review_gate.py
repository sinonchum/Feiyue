import pytest
from pydantic import ValidationError

from feiyue_core.curation.distillation_proposal import (
    DistillationProposal,
    ProposalPatch,
    ProposalStatus,
    build_distillation_proposal,
)
from feiyue_core.curation.review_gate import (
    InvalidReviewTransitionError,
    ReviewDecision,
    ReviewDecisionStatus,
    ReviewGate,
)


def _patch(**overrides: object) -> ProposalPatch:
    data = {
        "asset_type": "lesson",
        "target_path": "lessons/retry.md",
        "summary": "Capture a retry lesson.",
        "proposed_content": "Always retry flaky checks once.",
        "source_ids": ["trace-1"],
    }
    data.update(overrides)
    return ProposalPatch(**data)


def _proposal(**overrides: object) -> DistillationProposal:
    data = {
        "proposal_id": "proposal-1",
        "source_task_id": "task-1",
        "source_input_id": "input-1",
        "patches": [_patch()],
    }
    data.update(overrides)
    return build_distillation_proposal(**data)


def test_accept_review_required_proposal_returns_decision_with_default_sources() -> None:
    proposal = _proposal()

    decision = ReviewGate().accept(
        proposal,
        decision_id="decision-1",
        reviewer_id="reviewer-1",
        rationale="Looks safe and useful.",
    )

    assert decision == ReviewDecision(
        decision_id="decision-1",
        proposal_id="proposal-1",
        decision=ReviewDecisionStatus.ACCEPTED,
        reviewer_id="reviewer-1",
        rationale="Looks safe and useful.",
        source_ids=["proposal-1", "input-1", "task-1"],
    )
    assert decision.decision.value == "accepted"


def test_reject_draft_proposal_returns_decision_with_explicit_sources() -> None:
    proposal = DistillationProposal(
        proposal_id="proposal-draft",
        status=ProposalStatus.DRAFT,
        source_task_id="task-1",
        source_input_id="input-1",
        patches=[_patch()],
    )

    decision = ReviewGate().reject(
        proposal,
        decision_id="decision-2",
        reviewer_id="reviewer-1",
        rationale="Needs stronger evidence.",
        source_ids=["review-note-1"],
    )

    assert decision.decision is ReviewDecisionStatus.REJECTED
    assert decision.decision.value == "rejected"
    assert decision.proposal_id == "proposal-draft"
    assert decision.source_ids == ["review-note-1"]


def test_review_decision_validates_reviewer_rationale_and_source_ids() -> None:
    base = {
        "decision_id": "decision-1",
        "proposal_id": "proposal-1",
        "decision": ReviewDecisionStatus.ACCEPTED,
        "reviewer_id": "reviewer-1",
        "rationale": "Good rationale.",
        "source_ids": ["source-1"],
    }

    for field in ("reviewer_id", "rationale"):
        data = dict(base)
        data[field] = ""
        with pytest.raises(ValidationError, match=field):
            ReviewDecision(**data)

    with pytest.raises(ValidationError, match="source_ids"):
        ReviewDecision(**{**base, "source_ids": []})

    with pytest.raises(ValidationError, match="source_ids"):
        ReviewDecision(**{**base, "source_ids": ["source-1", ""]})


def test_review_gate_rejects_approved_or_invalid_proposal_status() -> None:
    approved = DistillationProposal.model_construct(
        proposal_id="proposal-approved",
        status=ProposalStatus.APPROVED,
        source_task_id="task-1",
        source_input_id="input-1",
        patches=[_patch()],
    )
    invalid = DistillationProposal.model_construct(
        proposal_id="proposal-invalid",
        status="invalid",
        source_task_id="task-1",
        source_input_id="input-1",
        patches=[_patch()],
    )

    gate = ReviewGate()
    for proposal in (approved, invalid):
        with pytest.raises(InvalidReviewTransitionError, match="cannot be reviewed"):
            gate.accept(
                proposal,
                decision_id="decision-1",
                reviewer_id="reviewer-1",
                rationale="A rationale.",
            )


def test_render_markdown_is_deterministic() -> None:
    decision = ReviewDecision(
        decision_id="decision-1",
        proposal_id="proposal-1",
        decision=ReviewDecisionStatus.REJECTED,
        reviewer_id="reviewer-1",
        rationale="Needs clearer sources.",
        source_ids=["proposal-1", "input-1", "task-1"],
    )

    assert decision.render_markdown() == (
        "# Review Decision: decision-1\n\n"
        "## Proposal\n\n"
        "proposal-1\n\n"
        "## Decision\n\n"
        "rejected\n\n"
        "## Reviewer\n\n"
        "reviewer-1\n\n"
        "## Rationale\n\n"
        "Needs clearer sources.\n\n"
        "## Source IDs\n\n"
        "- proposal-1\n"
        "- input-1\n"
        "- task-1\n"
    )
