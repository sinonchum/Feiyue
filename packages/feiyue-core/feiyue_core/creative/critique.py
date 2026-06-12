"""Provider-free creative critique schema.

Creative critiques evaluate candidate variants against supplied constraints and
source evidence. They are assessment artifacts only: this module does not promote
variants, mutate projects, or call providers/network services.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel


class CreativeCritiqueRecommendation(StrEnum):
    """Supported creative critique recommendations."""

    PURSUE = "pursue"
    REVISE = "revise"
    REJECT = "reject"
    DEFER = "defer"


class CreativeCritique(FeiyueModel):
    """A provider-free critique of a candidate creative variant."""

    critique_id: str
    variant_id: str
    constraint_violations: list[str] = Field(default_factory=list)
    risk_assessment: str
    feasibility_notes: str
    verification_cost: str
    recommendation: CreativeCritiqueRecommendation
    source_ids: list[str] = Field(min_length=1)

    @field_validator(
        "critique_id",
        "variant_id",
        "risk_assessment",
        "feasibility_notes",
        "verification_cost",
    )
    @classmethod
    def required_strings_must_not_be_empty(cls, value: str, info: Any) -> str:
        if value.strip() == "":
            raise ValueError(f"{info.field_name} must not be empty")
        return value

    @field_validator("constraint_violations")
    @classmethod
    def constraint_violations_must_not_contain_empty_values(
        cls, value: list[str]
    ) -> list[str]:
        if any(item.strip() == "" for item in value):
            raise ValueError("constraint_violations must not contain empty values")
        return value

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_not_contain_empty_values(cls, value: list[str]) -> list[str]:
        if any(source_id.strip() == "" for source_id in value):
            raise ValueError("source_ids must not contain empty values")
        return value

    def render_markdown(self) -> str:
        """Render this critique as deterministic Markdown."""

        sections = [
            f"# Creative Critique: {self.critique_id}",
            "\n".join(
                [
                    f"- Variant ID: {self.variant_id}",
                    f"- Recommendation: {self.recommendation.value}",
                ]
            ),
            "## Constraint Violations\n\n"
            + _render_bulleted_list(self.constraint_violations),
            f"## Risk Assessment\n\n{self.risk_assessment}",
            f"## Feasibility Notes\n\n{self.feasibility_notes}",
            f"## Verification Cost\n\n{self.verification_cost}",
            "## Source IDs\n\n" + _render_bulleted_list(self.source_ids),
        ]
        return "\n\n".join(sections) + "\n"


def _render_bulleted_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)
