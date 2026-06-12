import pytest
from pydantic import ValidationError

from feiyue_core.curation import TeacherGuidanceSummary, normalize_teacher_guidance


def test_normalize_teacher_guidance_uses_explicit_fields_and_bounds_raw_excerpt() -> None:
    summary = normalize_teacher_guidance(
        guidance_id="guidance-1",
        source_task_id="task-1",
        raw_guidance="0123456789ABCDE",
        source_ids=["trace-1", "teacher-note-1"],
        root_cause="The test relied on provider-specific wording.",
        minimal_fix_strategy="Assert stable behavior instead of prose.",
        prevention_rule="Do not snapshot provider prose.",
        suggested_asset_updates=["Update pytest verifier guidance.", "Add regression case."],
        max_raw_excerpt_chars=10,
    )

    assert summary == TeacherGuidanceSummary(
        guidance_id="guidance-1",
        source_task_id="task-1",
        root_cause="The test relied on provider-specific wording.",
        minimal_fix_strategy="Assert stable behavior instead of prose.",
        prevention_rule="Do not snapshot provider prose.",
        suggested_asset_updates=[
            "Update pytest verifier guidance.",
            "Add regression case.",
        ],
        bounded_raw_excerpt="0123456789... [truncated 5 chars]",
        source_ids=["trace-1", "teacher-note-1"],
    )


def test_teacher_guidance_summary_rejects_missing_or_empty_source_ids() -> None:
    with pytest.raises(ValidationError, match="source_ids"):
        TeacherGuidanceSummary(
            guidance_id="guidance-1",
            source_task_id="task-1",
            source_ids=[],
        )

    with pytest.raises(ValidationError, match="source_ids"):
        TeacherGuidanceSummary(
            guidance_id="guidance-1",
            source_task_id="task-1",
            source_ids=["trace-1", ""],
        )


def test_normalize_teacher_guidance_conservatively_extracts_simple_headings() -> None:
    raw_guidance = """Root Cause:
The implementation mutated shared defaults.

Minimal Fix Strategy:
Use default_factory for list fields.

Prevention Rule:
Never use a mutable literal as a model field default.

Suggested Asset Updates:
- Add a lesson about pydantic list defaults.
- Add a regression assertion.
"""

    summary = normalize_teacher_guidance(
        guidance_id="guidance-2",
        source_task_id="task-2",
        raw_guidance=raw_guidance,
        source_ids=["teacher-note-2"],
    )

    assert summary.root_cause == "The implementation mutated shared defaults."
    assert summary.minimal_fix_strategy == "Use default_factory for list fields."
    assert summary.prevention_rule == (
        "Never use a mutable literal as a model field default."
    )
    assert summary.suggested_asset_updates == [
        "Add a lesson about pydantic list defaults.",
        "Add a regression assertion.",
    ]


def test_normalize_teacher_guidance_does_not_hallucinate_without_headings() -> None:
    summary = normalize_teacher_guidance(
        guidance_id="guidance-3",
        source_task_id="task-3",
        raw_guidance="The teacher said the local loop failed after retries.",
        source_ids=["teacher-note-3"],
    )

    assert summary.root_cause is None
    assert summary.minimal_fix_strategy is None
    assert summary.prevention_rule is None
    assert summary.suggested_asset_updates == []
    assert summary.bounded_raw_excerpt == (
        "The teacher said the local loop failed after retries."
    )


def test_render_markdown_is_deterministic_and_renders_missing_values() -> None:
    summary = TeacherGuidanceSummary(
        guidance_id="guidance-4",
        source_task_id="task-4",
        root_cause="Bad fixture setup.",
        minimal_fix_strategy=None,
        prevention_rule=None,
        suggested_asset_updates=[],
        bounded_raw_excerpt=None,
        source_ids=["trace-4", "note-4"],
    )

    assert summary.render_markdown() == (
        "# Teacher Guidance Summary: guidance-4\n\n"
        "## Source Task\n\n"
        "task-4\n\n"
        "## Root Cause\n\n"
        "Bad fixture setup.\n\n"
        "## Minimal Fix Strategy\n\n"
        "- None\n\n"
        "## Prevention Rule\n\n"
        "- None\n\n"
        "## Suggested Asset Updates\n\n"
        "- None\n\n"
        "## Source IDs\n\n"
        "- trace-4\n"
        "- note-4\n\n"
        "## Bounded Raw Excerpt\n\n"
        "- None\n"
    )


def test_render_markdown_lists_asset_updates_and_raw_excerpt() -> None:
    summary = normalize_teacher_guidance(
        guidance_id="guidance-5",
        source_task_id="task-5",
        raw_guidance="raw teacher guidance",
        source_ids=["trace-5"],
        suggested_asset_updates=["Update lesson packet.", "Add eval."],
    )

    assert summary.render_markdown() == (
        "# Teacher Guidance Summary: guidance-5\n\n"
        "## Source Task\n\n"
        "task-5\n\n"
        "## Root Cause\n\n"
        "- None\n\n"
        "## Minimal Fix Strategy\n\n"
        "- None\n\n"
        "## Prevention Rule\n\n"
        "- None\n\n"
        "## Suggested Asset Updates\n\n"
        "- Update lesson packet.\n"
        "- Add eval.\n\n"
        "## Source IDs\n\n"
        "- trace-5\n\n"
        "## Bounded Raw Excerpt\n\n"
        "raw teacher guidance\n"
    )
