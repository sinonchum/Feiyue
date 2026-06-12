"""Provider-free creative brief schema.

Creative briefs are candidate design artifacts. This module only normalizes and
renders explicitly supplied fields; it does not promote a brief into PRDs or
implementation tasks and never calls providers or the network.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel


class CreativeBrief(FeiyueModel):
    """Candidate-only creative brief assembled from explicit project knowledge."""

    _LIST_FIELDS: ClassVar[tuple[str, ...]] = (
        "project_context",
        "design_laws",
        "non_goals",
        "constraints",
        "target_users",
        "desired_outcomes",
        "source_ids",
    )

    brief_id: str
    human_seed: str
    project_context: list[str] = Field(default_factory=list)
    design_laws: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    desired_outcomes: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(min_length=1)

    @field_validator("brief_id", "human_seed")
    @classmethod
    def required_strings_must_not_be_empty(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("value must not be empty")
        return normalized

    @field_validator(*_LIST_FIELDS)
    @classmethod
    def list_strings_must_not_contain_empty_entries(
        cls, value: list[str]
    ) -> list[str]:
        normalized_values: list[str] = []
        for item in value:
            normalized_item = item.strip()
            if normalized_item == "":
                raise ValueError("list fields must not contain empty entries")
            normalized_values.append(normalized_item)
        return normalized_values

    @classmethod
    def from_project_knowledge(
        cls,
        *,
        brief_id: str,
        human_seed: str,
        project_knowledge_markdown: str | None = None,
        context: str | Sequence[str] | None = None,
        design_laws: list[str] | None = None,
        non_goals: list[str] | None = None,
        constraints: list[str] | None = None,
        target_users: list[str] | None = None,
        desired_outcomes: list[str] | None = None,
        source_ids: list[str],
    ) -> "CreativeBrief":
        """Build a creative brief from explicitly supplied knowledge fields.

        This constructor is intentionally provider-free: supplied Markdown and
        context strings are copied into ``project_context`` without extracting or
        inferring additional facts.
        """

        project_context = _collect_project_context(
            project_knowledge_markdown=project_knowledge_markdown,
            context=context,
        )
        return cls(
            brief_id=brief_id,
            human_seed=human_seed,
            project_context=project_context,
            design_laws=design_laws or [],
            non_goals=non_goals or [],
            constraints=constraints or [],
            target_users=target_users or [],
            desired_outcomes=desired_outcomes or [],
            source_ids=source_ids,
        )

    def render_markdown(self) -> str:
        """Render this candidate brief as deterministic Markdown."""

        sections = [
            f"# Creative Brief: {self.brief_id}",
            f"## Human Seed\n\n{self.human_seed}",
            "## Project Context\n\n" + _render_bulleted_list(self.project_context),
            "## Design Laws\n\n" + _render_bulleted_list(self.design_laws),
            "## Non-Goals\n\n" + _render_bulleted_list(self.non_goals),
            "## Constraints\n\n" + _render_bulleted_list(self.constraints),
            "## Target Users\n\n" + _render_bulleted_list(self.target_users),
            "## Desired Outcomes\n\n" + _render_bulleted_list(self.desired_outcomes),
            "## Source IDs\n\n" + _render_bulleted_list(self.source_ids),
        ]
        return "\n\n".join(sections) + "\n"


def _collect_project_context(
    *,
    project_knowledge_markdown: str | None,
    context: str | Sequence[str] | None,
) -> list[str]:
    values: list[str] = []
    if project_knowledge_markdown is not None:
        values.append(project_knowledge_markdown)
    if context is None:
        return values
    if isinstance(context, str):
        values.append(context)
        return values
    values.extend(context)
    return values


def _render_bulleted_list(values: Sequence[str]) -> str:
    if not values:
        return "- None"
    return "\n".join(f"- {value}" for value in values)
