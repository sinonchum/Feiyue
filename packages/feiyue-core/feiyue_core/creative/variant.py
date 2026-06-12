"""Creative variant candidate schema.

Creative variants are provider-free proposal records. They are always candidate
artifacts and cannot promote work into PRDs or tasks on their own.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel


class CreativeVariantType(StrEnum):
    """Supported creative variant strategies."""

    CONSERVATIVE = "conservative"
    BOLD = "bold"
    LOW_COST = "low_cost"
    HIGH_IMPACT = "high_impact"


class CreativeVariant(FeiyueModel):
    """A candidate-only creative variant for a creative brief."""

    variant_id: str
    brief_id: str
    variant_type: CreativeVariantType
    pitch: str
    rationale: str
    risks: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    verification_idea: str
    required_capability_level: str
    source_ids: list[str] = Field(min_length=1)
    candidate_only: bool = True

    @field_validator(
        "variant_id",
        "brief_id",
        "pitch",
        "rationale",
        "verification_idea",
        "required_capability_level",
    )
    @classmethod
    def required_strings_must_not_be_empty(cls, value: str, info: Any) -> str:
        if value.strip() == "":
            raise ValueError(f"{info.field_name} must not be empty")
        return value

    @field_validator("risks", "non_goals")
    @classmethod
    def optional_list_items_must_not_be_empty(
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

    @field_validator("candidate_only")
    @classmethod
    def candidate_only_must_be_true(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("candidate_only must be true")
        return value

    def render_markdown(self) -> str:
        """Render this candidate variant as deterministic Markdown."""

        sections = [
            f"# Creative Variant: {self.variant_id}",
            "\n".join(
                [
                    f"- Brief ID: {self.brief_id}",
                    f"- Variant Type: {self.variant_type.value}",
                    "- Candidate Only: true",
                    f"- Required Capability Level: {self.required_capability_level}",
                ]
            ),
            f"## Pitch\n\n{self.pitch}",
            f"## Rationale\n\n{self.rationale}",
            "## Risks\n\n" + _render_bulleted_list(self.risks),
            "## Non-Goals\n\n" + _render_bulleted_list(self.non_goals),
            f"## Verification Idea\n\n{self.verification_idea}",
            "## Source IDs\n\n" + _render_bulleted_list(self.source_ids),
        ]
        return "\n\n".join(sections) + "\n"


def _render_bulleted_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)
