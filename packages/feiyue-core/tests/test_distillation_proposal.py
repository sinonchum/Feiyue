import pytest
from pydantic import ValidationError

from feiyue_core.curation.distillation_proposal import (
    DistillationProposal,
    ProposalPatch,
    ProposalStatus,
    build_distillation_proposal,
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


def test_build_distillation_proposal_defaults_to_review_required_not_approved() -> None:
    proposal = build_distillation_proposal(
        proposal_id="proposal-1",
        source_task_id="task-1",
        source_input_id="input-1",
        patches=[_patch()],
    )

    assert proposal.status is ProposalStatus.REVIEW_REQUIRED
    assert proposal.status.value == "review_required"
    assert proposal.status is not ProposalStatus.APPROVED


def test_proposal_rejects_approved_status_at_construction() -> None:
    draft = DistillationProposal(
        proposal_id="proposal-draft",
        status=ProposalStatus.DRAFT,
        source_task_id="task-1",
        source_input_id="input-1",
        patches=[_patch()],
    )
    assert draft.status is ProposalStatus.DRAFT

    with pytest.raises(ValidationError, match="approved"):
        DistillationProposal(
            proposal_id="proposal-1",
            status=ProposalStatus.APPROVED,
            source_task_id="task-1",
            source_input_id="input-1",
            patches=[_patch()],
        )


def test_patch_requires_allowed_asset_type_non_empty_source_ids_and_content() -> None:
    with pytest.raises(ValidationError, match="asset_type"):
        _patch(asset_type="unknown")

    with pytest.raises(ValidationError, match="source_ids"):
        _patch(source_ids=[])

    with pytest.raises(ValidationError, match="proposed_content"):
        _patch(proposed_content="")


def test_render_markdown_is_deterministic_and_includes_patch_details() -> None:
    proposal = build_distillation_proposal(
        proposal_id="proposal-1",
        source_task_id="task-1",
        source_input_id="input-1",
        patches=[
            _patch(
                asset_type="task_template",
                target_path=None,
                summary="Add a deterministic task template.",
                proposed_content="## Template\nUse local fixtures.",
                source_ids=["trace-1", "trace-2"],
            ),
            _patch(
                asset_type="routing_rule",
                target_path="routing/rules.md",
                summary="Route tiny tasks locally.",
                proposed_content="Prefer local model for tiny deterministic edits.",
                source_ids=["trace-3"],
            ),
        ],
    )

    assert proposal.render_markdown() == (
        "# Distillation Proposal: proposal-1\n\n"
        "## Status\n\n"
        "review_required\n\n"
        "## Source Task\n\n"
        "task-1\n\n"
        "## Source Input\n\n"
        "input-1\n\n"
        "## Proposed Patches\n\n"
        "### Patch 1\n\n"
        "- Patch ID: index:0\n"
        "- Asset Type: task_template\n"
        "- Target Path: None\n"
        "- Summary: Add a deterministic task template.\n"
        "- Source IDs: trace-1, trace-2\n\n"
        "```\n"
        "## Template\nUse local fixtures.\n"
        "```\n\n"
        "### Patch 2\n\n"
        "- Patch ID: index:1\n"
        "- Asset Type: routing_rule\n"
        "- Target Path: routing/rules.md\n"
        "- Summary: Route tiny tasks locally.\n"
        "- Source IDs: trace-3\n\n"
        "```\n"
        "Prefer local model for tiny deterministic edits.\n"
        "```\n"
    )


def test_all_allowed_asset_types_are_accepted() -> None:
    allowed = [
        "lesson",
        "task_template",
        "regression_eval",
        "skill",
        "project_memory",
        "routing_rule",
    ]

    assert [_patch(asset_type=asset_type).asset_type for asset_type in allowed] == allowed
