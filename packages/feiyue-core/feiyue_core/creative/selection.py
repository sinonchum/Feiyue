"""User selection feedback schema for creative variants.

Selection feedback is an evidence-only record of a user's choice. It never
mutates project memory, PRDs, or task state and performs no provider calls.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from feiyue_core.schemas.common import FeiyueModel


class UserSelectionStatus(StrEnum):
    """Supported user selection outcomes."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class UserSelectionFeedback(FeiyueModel):
    """Evidence-only feedback about a user's selected creative variant."""

    feedback_id: str
    brief_id: str
    selected_variant_id: str | None = None
    status: UserSelectionStatus
    rationale: str
    violated_design_laws: list[str] = Field(default_factory=list)
    useful_aspects: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(min_length=1)

    @field_validator("feedback_id", "brief_id", "rationale")
    @classmethod
    def required_strings_must_not_be_empty(cls, value: str, info: Any) -> str:
        if value.strip() == "":
            raise ValueError(f"{info.field_name} must not be empty")
        return value

    @field_validator("violated_design_laws", "useful_aspects")
    @classmethod
    def list_strings_must_not_contain_empty_values(
        cls, value: list[str], info: Any
    ) -> list[str]:
        if any(item.strip() == "" for item in value):
            raise ValueError(f"{info.field_name} must not contain empty values")
        return value

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_not_contain_empty_values(cls, value: list[str]) -> list[str]:
        if any(source_id.strip() == "" for source_id in value):
            raise ValueError("source_ids must not contain empty values")
        return value

    @model_validator(mode="after")
    def selected_variant_id_must_match_status(self) -> "UserSelectionFeedback":
        if self.status is UserSelectionStatus.ACCEPTED and (
            self.selected_variant_id is None or self.selected_variant_id.strip() == ""
        ):
            raise ValueError(
                "selected_variant_id must not be empty for accepted feedback"
            )
        if (
            self.status is not UserSelectionStatus.ACCEPTED
            and self.selected_variant_id is not None
            and self.selected_variant_id.strip() == ""
        ):
            raise ValueError("selected_variant_id must not be empty")
        return self

    def render_markdown(self) -> str:
        """Render this selection feedback as deterministic Markdown."""

        selected_variant = self.selected_variant_id
        if selected_variant is None:
            selected_variant = "None"
        sections = [
            f"# User Selection Feedback: {self.feedback_id}",
            "\n".join(
                [
                    f"- Brief ID: {self.brief_id}",
                    f"- Selected Variant ID: {selected_variant}",
                    f"- Status: {self.status.value}",
                ]
            ),
            f"## Rationale\n\n{self.rationale}",
            "## Violated Design Laws\n\n"
            + _render_bulleted_list(self.violated_design_laws),
            "## Useful Aspects\n\n" + _render_bulleted_list(self.useful_aspects),
            "## Source IDs\n\n" + _render_bulleted_list(self.source_ids),
        ]
        return "\n\n".join(sections) + "\n"


def _render_bulleted_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)
