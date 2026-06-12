from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.creative import CreativeVariant, CreativeVariantType


def make_variant(**overrides: object) -> CreativeVariant:
    data: dict[str, object] = {
        "variant_id": "variant-1",
        "brief_id": "brief-1",
        "variant_type": CreativeVariantType.BOLD,
        "pitch": "Lead with an interactive migration checklist.",
        "rationale": "It gives reviewers a concrete way to compare options.",
        "risks": ["May take extra implementation time."],
        "non_goals": ["Do not select a provider."],
        "verification_idea": "Review the generated checklist against acceptance criteria.",
        "required_capability_level": "L2",
        "source_ids": ["source-1", "source-2"],
    }
    data.update(overrides)
    return CreativeVariant(**data)


def test_creative_variant_type_values_are_stable() -> None:
    assert [variant_type.value for variant_type in CreativeVariantType] == [
        "conservative",
        "bold",
        "low_cost",
        "high_impact",
    ]


def test_creative_variant_accepts_string_variant_type_and_defaults_candidate_only() -> None:
    variant = make_variant(variant_type="low_cost", risks=[], non_goals=[])

    assert variant.variant_type is CreativeVariantType.LOW_COST
    assert variant.candidate_only is True
    assert variant.risks == []
    assert variant.non_goals == []


def test_candidate_only_false_is_rejected() -> None:
    with pytest.raises(ValidationError, match="candidate_only must be true"):
        make_variant(candidate_only=False)


@pytest.mark.parametrize(
    "field_name",
    [
        "variant_id",
        "brief_id",
        "pitch",
        "rationale",
        "verification_idea",
        "required_capability_level",
    ],
)
def test_required_strings_must_be_non_empty(field_name: str) -> None:
    with pytest.raises(ValidationError, match=f"{field_name} must not be empty"):
        make_variant(**{field_name: ""})


def test_required_strings_must_not_be_whitespace_only() -> None:
    with pytest.raises(ValidationError, match="pitch must not be empty"):
        make_variant(pitch="   ")


@pytest.mark.parametrize("field_name", ["risks", "non_goals"])
def test_list_string_fields_reject_empty_entries(field_name: str) -> None:
    with pytest.raises(ValidationError, match=f"{field_name} must not contain empty values"):
        make_variant(**{field_name: ["valid", ""]})

    with pytest.raises(ValidationError, match=f"{field_name} must not contain empty values"):
        make_variant(**{field_name: ["valid", "   "]})


def test_source_ids_must_be_non_empty_and_contain_no_empty_ids() -> None:
    with pytest.raises(ValidationError):
        make_variant(source_ids=[])

    with pytest.raises(ValidationError, match="source_ids must not contain empty values"):
        make_variant(source_ids=["source-1", ""])

    with pytest.raises(ValidationError, match="source_ids must not contain empty values"):
        make_variant(source_ids=["source-1", "   "])


def test_list_defaults_are_not_shared() -> None:
    first = make_variant(risks=[], non_goals=[])
    second = make_variant(risks=[], non_goals=[])

    first.risks.append("first-only risk")
    first.non_goals.append("first-only non-goal")

    assert second.risks == []
    assert second.non_goals == []


def test_render_markdown_is_deterministic() -> None:
    variant = make_variant()

    assert variant.render_markdown() == (
        "# Creative Variant: variant-1\n\n"
        "- Brief ID: brief-1\n"
        "- Variant Type: bold\n"
        "- Candidate Only: true\n"
        "- Required Capability Level: L2\n\n"
        "## Pitch\n\n"
        "Lead with an interactive migration checklist.\n\n"
        "## Rationale\n\n"
        "It gives reviewers a concrete way to compare options.\n\n"
        "## Risks\n\n"
        "- May take extra implementation time.\n\n"
        "## Non-Goals\n\n"
        "- Do not select a provider.\n\n"
        "## Verification Idea\n\n"
        "Review the generated checklist against acceptance criteria.\n\n"
        "## Source IDs\n\n"
        "- source-1\n"
        "- source-2\n"
    )


def test_render_markdown_renders_empty_lists_as_none() -> None:
    variant = make_variant(risks=[], non_goals=[])

    markdown = variant.render_markdown()

    assert "## Risks\n\n- None\n\n" in markdown
    assert "## Non-Goals\n\n- None\n\n" in markdown
