"""Provider-free teacher guidance normalization.

This module turns free-form teacher notes into a conservative summary for later
curation review. It never calls providers: explicit fields are used as supplied,
and free-form text is only parsed when simple, recognizable headings are present.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel

DEFAULT_MAX_RAW_EXCERPT_CHARS = 2000

_HEADING_TO_FIELD = {
    "root cause": "root_cause",
    "minimal fix strategy": "minimal_fix_strategy",
    "prevention rule": "prevention_rule",
    "suggested asset updates": "suggested_asset_updates",
}


class TeacherGuidanceSummary(FeiyueModel):
    """Conservative, provider-free summary of teacher guidance."""

    guidance_id: str
    source_task_id: str
    root_cause: str | None = None
    minimal_fix_strategy: str | None = None
    prevention_rule: str | None = None
    suggested_asset_updates: list[str] = Field(default_factory=list)
    bounded_raw_excerpt: str | None = None
    source_ids: list[str] = Field(min_length=1)

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_not_contain_empty_values(cls, value: list[str]) -> list[str]:
        if any(source_id == "" for source_id in value):
            raise ValueError("source_ids must not contain empty values")
        return value

    @classmethod
    def from_text(
        cls,
        *,
        guidance_id: str,
        source_task_id: str,
        raw_guidance: str,
        source_ids: list[str],
        root_cause: str | None = None,
        minimal_fix_strategy: str | None = None,
        prevention_rule: str | None = None,
        suggested_asset_updates: list[str] | None = None,
        max_raw_excerpt_chars: int = DEFAULT_MAX_RAW_EXCERPT_CHARS,
    ) -> "TeacherGuidanceSummary":
        """Build a summary from explicit fields plus conservative heading parsing."""

        extracted = _extract_heading_sections(raw_guidance)
        updates = suggested_asset_updates
        if updates is None:
            updates = _parse_asset_updates(extracted.get("suggested_asset_updates"))

        return cls(
            guidance_id=guidance_id,
            source_task_id=source_task_id,
            root_cause=root_cause if root_cause is not None else extracted.get("root_cause"),
            minimal_fix_strategy=(
                minimal_fix_strategy
                if minimal_fix_strategy is not None
                else extracted.get("minimal_fix_strategy")
            ),
            prevention_rule=(
                prevention_rule
                if prevention_rule is not None
                else extracted.get("prevention_rule")
            ),
            suggested_asset_updates=updates,
            bounded_raw_excerpt=_truncate_text(
                raw_guidance,
                max_raw_excerpt_chars,
                parameter_name="max_raw_excerpt_chars",
            ),
            source_ids=source_ids,
        )

    def render_markdown(self) -> str:
        """Render this summary as deterministic Markdown for curation review."""

        sections = [
            f"# Teacher Guidance Summary: {self.guidance_id}",
            f"## Source Task\n\n{self.source_task_id}",
            f"## Root Cause\n\n{_render_optional_scalar(self.root_cause)}",
            "## Minimal Fix Strategy\n\n"
            + _render_optional_scalar(self.minimal_fix_strategy),
            f"## Prevention Rule\n\n{_render_optional_scalar(self.prevention_rule)}",
            "## Suggested Asset Updates\n\n"
            + _render_bulleted_list(self.suggested_asset_updates),
            "## Source IDs\n\n" + _render_bulleted_list(self.source_ids),
            "## Bounded Raw Excerpt\n\n"
            + _render_optional_scalar(self.bounded_raw_excerpt),
        ]
        return "\n\n".join(sections) + "\n"


def normalize_teacher_guidance(
    *,
    guidance_id: str,
    source_task_id: str,
    raw_guidance: str,
    source_ids: list[str],
    root_cause: str | None = None,
    minimal_fix_strategy: str | None = None,
    prevention_rule: str | None = None,
    suggested_asset_updates: list[str] | None = None,
    max_raw_excerpt_chars: int = DEFAULT_MAX_RAW_EXCERPT_CHARS,
) -> TeacherGuidanceSummary:
    """Normalize teacher guidance without any provider or network dependency."""

    return TeacherGuidanceSummary.from_text(
        guidance_id=guidance_id,
        source_task_id=source_task_id,
        raw_guidance=raw_guidance,
        source_ids=source_ids,
        root_cause=root_cause,
        minimal_fix_strategy=minimal_fix_strategy,
        prevention_rule=prevention_rule,
        suggested_asset_updates=suggested_asset_updates,
        max_raw_excerpt_chars=max_raw_excerpt_chars,
    )


def _extract_heading_sections(raw_guidance: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_field: str | None = None

    for line in raw_guidance.splitlines():
        heading = _parse_heading_line(line)
        if heading is not None:
            current_field, remainder = heading
            sections.setdefault(current_field, [])
            if remainder:
                sections[current_field].append(remainder)
            continue
        if current_field is not None:
            sections[current_field].append(line)

    return {
        field: text
        for field, lines in sections.items()
        if (text := "\n".join(lines).strip()) != ""
    }


def _parse_heading_line(line: str) -> tuple[str, str] | None:
    candidate = line.strip()
    while candidate.startswith("#"):
        candidate = candidate[1:].strip()

    candidate_lower = candidate.casefold()
    for heading, field in _HEADING_TO_FIELD.items():
        if candidate_lower == heading:
            return field, ""
        prefix = f"{heading}:"
        if candidate_lower.startswith(prefix):
            return field, candidate[len(prefix) :].strip()
    return None


def _parse_asset_updates(value: str | None) -> list[str]:
    if value is None:
        return []

    updates: list[str] = []
    for line in value.splitlines():
        item = line.strip()
        if not item:
            continue
        for marker in ("- ", "* ", "+ "):
            if item.startswith(marker):
                item = item[len(marker) :].strip()
                break
        updates.append(item)
    return updates


def _render_optional_scalar(value: str | None) -> str:
    if value is None:
        return "- None"
    return value


def _render_bulleted_list(values: Sequence[str]) -> str:
    if not values:
        return "- None"
    return "\n".join(f"- {value}" for value in values)


def _truncate_text(value: str, max_chars: int, *, parameter_name: str) -> str:
    if max_chars < 0:
        raise ValueError(f"{parameter_name} must be non-negative")
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"{value[:max_chars]}... [truncated {omitted} chars]"
