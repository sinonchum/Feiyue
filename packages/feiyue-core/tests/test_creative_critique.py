from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.creative import CreativeCritique, CreativeCritiqueRecommendation


def make_critique(**overrides: object) -> CreativeCritique:
    data: dict[str, object] = {
        "critique_id": "critique-1",
        "variant_id": "variant-1",
        "constraint_violations": ["Exceeds the no-network constraint."],
        "risk_assessment": "Medium risk because it changes onboarding flow.",
        "feasibility_notes": "Feasible with existing UI components.",
        "verification_cost": "One reviewer-hour plus local regression tests.",
        "recommendation": CreativeCritiqueRecommendation.REVISE,
        "source_ids": ["brief-1", "variant-1"],
    }
    data.update(overrides)
    return CreativeCritique(**data)


def test_creative_critique_recommendation_values_are_stable() -> None:
    assert [recommendation.value for recommendation in CreativeCritiqueRecommendation] == [
        "pursue",
        "revise",
        "reject",
        "defer",
    ]


def test_creative_critique_accepts_string_recommendation_and_defaults_lists() -> None:
    critique = make_critique(recommendation="pursue", constraint_violations=[])

    assert critique.recommendation is CreativeCritiqueRecommendation.PURSUE
    assert critique.constraint_violations == []


@pytest.mark.parametrize(
    "field_name",
    [
        "critique_id",
        "variant_id",
        "risk_assessment",
        "feasibility_notes",
        "verification_cost",
    ],
)
def test_required_strings_must_be_non_empty(field_name: str) -> None:
    with pytest.raises(ValidationError, match=f"{field_name} must not be empty"):
        make_critique(**{field_name: ""})

    with pytest.raises(ValidationError, match=f"{field_name} must not be empty"):
        make_critique(**{field_name: "   "})


def test_constraint_violations_reject_empty_entries() -> None:
    with pytest.raises(
        ValidationError, match="constraint_violations must not contain empty values"
    ):
        make_critique(constraint_violations=["valid", ""])

    with pytest.raises(
        ValidationError, match="constraint_violations must not contain empty values"
    ):
        make_critique(constraint_violations=["valid", "   "])


def test_source_ids_must_be_non_empty_and_contain_no_empty_ids() -> None:
    with pytest.raises(ValidationError):
        make_critique(source_ids=[])

    with pytest.raises(ValidationError, match="source_ids must not contain empty values"):
        make_critique(source_ids=["source-1", ""])

    with pytest.raises(ValidationError, match="source_ids must not contain empty values"):
        make_critique(source_ids=["source-1", "   "])


def test_list_defaults_are_not_shared() -> None:
    first = make_critique(constraint_violations=[])
    second = make_critique(constraint_violations=[])

    first.constraint_violations.append("first-only violation")

    assert second.constraint_violations == []


def test_render_markdown_is_deterministic() -> None:
    critique = make_critique()

    assert critique.render_markdown() == (
        "# Creative Critique: critique-1\n\n"
        "- Variant ID: variant-1\n"
        "- Recommendation: revise\n\n"
        "## Constraint Violations\n\n"
        "- Exceeds the no-network constraint.\n\n"
        "## Risk Assessment\n\n"
        "Medium risk because it changes onboarding flow.\n\n"
        "## Feasibility Notes\n\n"
        "Feasible with existing UI components.\n\n"
        "## Verification Cost\n\n"
        "One reviewer-hour plus local regression tests.\n\n"
        "## Source IDs\n\n"
        "- brief-1\n"
        "- variant-1\n"
    )


def test_render_markdown_renders_empty_lists_as_none() -> None:
    critique = make_critique(constraint_violations=[])

    assert "## Constraint Violations\n\n- None\n\n" in critique.render_markdown()
