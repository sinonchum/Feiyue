"""Provider-free distillation proposal models.

Distillation proposals collect candidate curation patches produced from task
outputs. They are intentionally review-first: new proposals default to
``review_required`` and cannot be constructed as approved.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel

AllowedAssetType = Literal[
    "lesson",
    "task_template",
    "regression_eval",
    "skill",
    "project_memory",
    "routing_rule",
]

ALLOWED_ASSET_TYPES: tuple[str, ...] = (
    "lesson",
    "task_template",
    "regression_eval",
    "skill",
    "project_memory",
    "routing_rule",
)


class ProposalStatus(StrEnum):
    """Review lifecycle status for distillation proposals."""

    REVIEW_REQUIRED = "review_required"
    DRAFT = "draft"
    APPROVED = "approved"


class ProposalPatch(FeiyueModel):
    """A single proposed curation asset change."""

    asset_type: AllowedAssetType
    target_path: str | None = None
    summary: str
    proposed_content: str
    source_ids: list[str] = Field(min_length=1)

    @field_validator("proposed_content")
    @classmethod
    def proposed_content_must_not_be_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("proposed_content must not be empty")
        return value

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_not_contain_empty_values(cls, value: list[str]) -> list[str]:
        if any(source_id == "" for source_id in value):
            raise ValueError("source_ids must not contain empty values")
        return value


class DistillationProposal(FeiyueModel):
    """Review-first bundle of proposed distillation patches."""

    proposal_id: str
    status: ProposalStatus = ProposalStatus.REVIEW_REQUIRED
    source_task_id: str
    source_input_id: str
    patches: list[ProposalPatch]

    @field_validator("status")
    @classmethod
    def status_must_not_be_approved(cls, value: ProposalStatus) -> ProposalStatus:
        if value is ProposalStatus.APPROVED:
            raise ValueError("approved status is not allowed when constructing a proposal")
        return value

    def render_markdown(self) -> str:
        """Render this proposal as deterministic Markdown for human review."""

        parts = [
            f"# Distillation Proposal: {self.proposal_id}",
            f"## Status\n\n{self.status.value}",
            f"## Source Task\n\n{self.source_task_id}",
            f"## Source Input\n\n{self.source_input_id}",
            "## Proposed Patches",
        ]

        for index, patch in enumerate(self.patches, start=1):
            source_ids = ", ".join(patch.source_ids)
            target_path = patch.target_path if patch.target_path is not None else "None"
            parts.append(
                "\n".join(
                    [
                        f"### Patch {index}",
                        "",
                        f"- Asset Type: {patch.asset_type}",
                        f"- Target Path: {target_path}",
                        f"- Summary: {patch.summary}",
                        f"- Source IDs: {source_ids}",
                        "",
                        "```",
                        patch.proposed_content,
                        "```",
                    ]
                )
            )

        return "\n\n".join(parts) + "\n"


def build_distillation_proposal(
    *,
    proposal_id: str,
    source_task_id: str,
    source_input_id: str,
    patches: list[ProposalPatch],
) -> DistillationProposal:
    """Build a review-required distillation proposal from explicit patches."""

    return DistillationProposal(
        proposal_id=proposal_id,
        status=ProposalStatus.REVIEW_REQUIRED,
        source_task_id=source_task_id,
        source_input_id=source_input_id,
        patches=patches,
    )
