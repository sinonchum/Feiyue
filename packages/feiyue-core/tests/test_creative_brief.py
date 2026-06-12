from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.creative.brief import CreativeBrief


def test_creative_brief_validates_required_non_empty_fields() -> None:
    with pytest.raises(ValidationError):
        CreativeBrief(brief_id="", human_seed="seed", source_ids=["src-1"])

    with pytest.raises(ValidationError):
        CreativeBrief(brief_id="brief-1", human_seed="   ", source_ids=["src-1"])

    with pytest.raises(ValidationError):
        CreativeBrief(brief_id="brief-1", human_seed="seed", source_ids=[])

    with pytest.raises(ValidationError):
        CreativeBrief(brief_id="brief-1", human_seed="seed", source_ids=["src-1", ""])


def test_creative_brief_validates_empty_entries_in_all_string_lists() -> None:
    list_fields = [
        "project_context",
        "design_laws",
        "non_goals",
        "constraints",
        "target_users",
        "desired_outcomes",
        "source_ids",
    ]

    for field_name in list_fields:
        kwargs = {
            "brief_id": "brief-1",
            "human_seed": "seed",
            "source_ids": ["src-1"],
            field_name: ["valid", "  "],
        }
        if field_name == "source_ids":
            kwargs["source_ids"] = ["src-1", "  "]

        with pytest.raises(ValidationError):
            CreativeBrief(**kwargs)


def test_from_project_knowledge_uses_only_supplied_fields() -> None:
    brief = CreativeBrief.from_project_knowledge(
        brief_id="brief-1",
        human_seed="Improve onboarding clarity",
        project_knowledge_markdown="# Project Knowledge\n\nExisting onboarding is dense.",
        design_laws=["Prefer explicit user control."],
        non_goals=["Do not redesign billing."],
        constraints=["Must work without network."],
        target_users=["First-time operators"],
        desired_outcomes=["Users complete setup unaided."],
        source_ids=["project-memory.md", "design-laws.md"],
    )

    assert brief == CreativeBrief(
        brief_id="brief-1",
        human_seed="Improve onboarding clarity",
        project_context=["# Project Knowledge\n\nExisting onboarding is dense."],
        design_laws=["Prefer explicit user control."],
        non_goals=["Do not redesign billing."],
        constraints=["Must work without network."],
        target_users=["First-time operators"],
        desired_outcomes=["Users complete setup unaided."],
        source_ids=["project-memory.md", "design-laws.md"],
    )


def test_from_project_knowledge_accepts_context_string_or_strings() -> None:
    from_single_context = CreativeBrief.from_project_knowledge(
        brief_id="brief-single",
        human_seed="seed",
        context="One supplied context block.",
        source_ids=["src-1"],
    )
    assert from_single_context.project_context == ["One supplied context block."]

    from_multiple_contexts = CreativeBrief.from_project_knowledge(
        brief_id="brief-multiple",
        human_seed="seed",
        context=["First supplied context block.", "Second supplied context block."],
        source_ids=["src-1"],
    )
    assert from_multiple_contexts.project_context == [
        "First supplied context block.",
        "Second supplied context block.",
    ]


def test_render_markdown_is_deterministic_and_renders_empty_lists_as_none() -> None:
    brief = CreativeBrief(
        brief_id="brief-1",
        human_seed="Improve onboarding clarity",
        project_context=["Existing onboarding is dense."],
        constraints=["Must work without network."],
        desired_outcomes=["Users complete setup unaided."],
        source_ids=["src-1"],
    )

    assert brief.render_markdown() == (
        "# Creative Brief: brief-1\n\n"
        "## Human Seed\n\n"
        "Improve onboarding clarity\n\n"
        "## Project Context\n\n"
        "- Existing onboarding is dense.\n\n"
        "## Design Laws\n\n"
        "- None\n\n"
        "## Non-Goals\n\n"
        "- None\n\n"
        "## Constraints\n\n"
        "- Must work without network.\n\n"
        "## Target Users\n\n"
        "- None\n\n"
        "## Desired Outcomes\n\n"
        "- Users complete setup unaided.\n\n"
        "## Source IDs\n\n"
        "- src-1\n"
    )


def test_list_defaults_are_not_shared() -> None:
    first = CreativeBrief(brief_id="brief-1", human_seed="seed", source_ids=["src-1"])
    second = CreativeBrief(brief_id="brief-2", human_seed="seed", source_ids=["src-2"])

    first.project_context.append("mutated")

    assert second.project_context == []
