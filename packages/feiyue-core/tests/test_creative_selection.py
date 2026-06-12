from __future__ import annotations

import pytest
from pydantic import ValidationError

from feiyue_core.creative import UserSelectionFeedback, UserSelectionStatus


def make_feedback(**overrides: object) -> UserSelectionFeedback:
    data: dict[str, object] = {
        "feedback_id": "feedback-1",
        "brief_id": "brief-1",
        "selected_variant_id": "variant-1",
        "status": UserSelectionStatus.ACCEPTED,
        "rationale": "This variant best satisfies the design laws.",
        "violated_design_laws": ["Keep the critical path short."],
        "useful_aspects": ["Clear verification path."],
        "source_ids": ["source-1", "source-2"],
    }
    data.update(overrides)
    return UserSelectionFeedback(**data)


def test_user_selection_status_values_are_stable() -> None:
    assert [status.value for status in UserSelectionStatus] == [
        "accepted",
        "rejected",
        "deferred",
    ]


def test_feedback_accepts_string_status_and_default_lists() -> None:
    feedback = make_feedback(
        status="rejected",
        selected_variant_id=None,
        violated_design_laws=[],
        useful_aspects=[],
    )

    assert feedback.status is UserSelectionStatus.REJECTED
    assert feedback.selected_variant_id is None
    assert feedback.violated_design_laws == []
    assert feedback.useful_aspects == []


@pytest.mark.parametrize("field_name", ["feedback_id", "brief_id", "rationale"])
def test_required_strings_must_be_non_empty(field_name: str) -> None:
    with pytest.raises(ValidationError, match=f"{field_name} must not be empty"):
        make_feedback(**{field_name: ""})

    with pytest.raises(ValidationError, match=f"{field_name} must not be empty"):
        make_feedback(**{field_name: "   "})


def test_accepted_feedback_requires_non_empty_selected_variant_id() -> None:
    with pytest.raises(
        ValidationError, match="selected_variant_id must not be empty for accepted feedback"
    ):
        make_feedback(selected_variant_id=None)

    with pytest.raises(
        ValidationError, match="selected_variant_id must not be empty for accepted feedback"
    ):
        make_feedback(selected_variant_id="")

    with pytest.raises(
        ValidationError, match="selected_variant_id must not be empty for accepted feedback"
    ):
        make_feedback(selected_variant_id="   ")


@pytest.mark.parametrize("status", [UserSelectionStatus.REJECTED, UserSelectionStatus.DEFERRED])
def test_rejected_and_deferred_feedback_allow_missing_selected_variant_id(
    status: UserSelectionStatus,
) -> None:
    feedback = make_feedback(status=status, selected_variant_id=None)

    assert feedback.selected_variant_id is None


@pytest.mark.parametrize("status", [UserSelectionStatus.REJECTED, UserSelectionStatus.DEFERRED])
def test_rejected_and_deferred_feedback_reject_empty_selected_variant_id(
    status: UserSelectionStatus,
) -> None:
    with pytest.raises(ValidationError, match="selected_variant_id must not be empty"):
        make_feedback(status=status, selected_variant_id="")

    with pytest.raises(ValidationError, match="selected_variant_id must not be empty"):
        make_feedback(status=status, selected_variant_id="   ")


@pytest.mark.parametrize("field_name", ["violated_design_laws", "useful_aspects"])
def test_list_string_fields_reject_empty_entries(field_name: str) -> None:
    with pytest.raises(ValidationError, match=f"{field_name} must not contain empty values"):
        make_feedback(**{field_name: ["valid", ""]})

    with pytest.raises(ValidationError, match=f"{field_name} must not contain empty values"):
        make_feedback(**{field_name: ["valid", "   "]})


def test_source_ids_must_be_non_empty_and_contain_no_empty_ids() -> None:
    with pytest.raises(ValidationError):
        make_feedback(source_ids=[])

    with pytest.raises(ValidationError, match="source_ids must not contain empty values"):
        make_feedback(source_ids=["source-1", ""])

    with pytest.raises(ValidationError, match="source_ids must not contain empty values"):
        make_feedback(source_ids=["source-1", "   "])


def test_list_defaults_are_not_shared() -> None:
    first = make_feedback(violated_design_laws=[], useful_aspects=[])
    second = make_feedback(violated_design_laws=[], useful_aspects=[])

    first.violated_design_laws.append("first-only law")
    first.useful_aspects.append("first-only aspect")

    assert second.violated_design_laws == []
    assert second.useful_aspects == []


def test_render_markdown_is_deterministic() -> None:
    feedback = make_feedback()

    assert feedback.render_markdown() == (
        "# User Selection Feedback: feedback-1\n\n"
        "- Brief ID: brief-1\n"
        "- Selected Variant ID: variant-1\n"
        "- Status: accepted\n\n"
        "## Rationale\n\n"
        "This variant best satisfies the design laws.\n\n"
        "## Violated Design Laws\n\n"
        "- Keep the critical path short.\n\n"
        "## Useful Aspects\n\n"
        "- Clear verification path.\n\n"
        "## Source IDs\n\n"
        "- source-1\n"
        "- source-2\n"
    )


def test_render_markdown_renders_none_selected_variant_and_empty_lists_as_none() -> None:
    feedback = make_feedback(
        status=UserSelectionStatus.DEFERRED,
        selected_variant_id=None,
        violated_design_laws=[],
        useful_aspects=[],
    )

    assert feedback.render_markdown() == (
        "# User Selection Feedback: feedback-1\n\n"
        "- Brief ID: brief-1\n"
        "- Selected Variant ID: None\n"
        "- Status: deferred\n\n"
        "## Rationale\n\n"
        "This variant best satisfies the design laws.\n\n"
        "## Violated Design Laws\n\n"
        "- None\n\n"
        "## Useful Aspects\n\n"
        "- None\n\n"
        "## Source IDs\n\n"
        "- source-1\n"
        "- source-2\n"
    )
