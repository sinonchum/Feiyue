from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator, model_validator

from feiyue_core.schemas.common import FeiyueModel


class CapabilityLevel(StrEnum):
    """Ordered capability levels from the Master Blueprint ladder."""

    READ_ONLY_AUDIT = "read_only_audit"
    DOCUMENTATION_BOILERPLATE = "documentation_boilerplate"
    SINGLE_FILE_CHANGE = "single_file_change"
    LOCALIZED_MULTI_FILE_CHANGE = "localized_multi_file_change"
    BOUNDED_DEBUG = "bounded_debug"
    MODULE_FEATURE_SLICE = "module_feature_slice"
    TEACHER_ASSISTED_COMPLEX_REPAIR = "teacher_assisted_complex_repair"
    IMPLEMENTATION_OPTIONS = "implementation_options"
    TASTE_AWARE_CREATIVE_VARIANTS = "taste_aware_creative_variants"


class CapabilityLevelDefinition(FeiyueModel):
    """Human-readable definition and evidence standard for one ladder level."""

    level: CapabilityLevel
    rank: int
    title: str
    description: str
    typical_tasks: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)


class CapabilityLadder(FeiyueModel):
    """Ordered capability ladder with contiguous ranks and unique levels."""

    definitions: list[CapabilityLevelDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_levels_and_contiguous_ranks(self) -> CapabilityLadder:
        levels = [definition.level for definition in self.definitions]
        if len(levels) != len(set(levels)):
            raise ValueError("Capability ladder definitions must have unique levels")

        ranks = sorted(definition.rank for definition in self.definitions)
        expected_ranks = list(range(len(self.definitions)))
        if ranks != expected_ranks:
            raise ValueError("Capability ladder ranks must be contiguous starting at 0")

        return self

    def render_markdown(self) -> str:
        """Render deterministic Markdown for the ladder in rank order."""
        lines = ["# Capability Ladder"]
        for definition in sorted(self.definitions, key=lambda item: item.rank):
            lines.extend(
                [
                    "",
                    f"## {definition.rank}. {definition.title} (`{definition.level.value}`)",
                    definition.description,
                    "",
                    "**Typical tasks:**",
                    *_render_list(definition.typical_tasks),
                    "",
                    "**Required evidence:**",
                    *_render_list(definition.required_evidence),
                ]
            )
        return "\n".join(lines)


class TaskComplexity(FeiyueModel):
    """Assessment of the capability level required for a task."""

    task_id: str
    required_level: CapabilityLevel
    rationale: str
    source_ids: list[str]

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, source_ids: list[str]) -> list[str]:
        if not source_ids:
            raise ValueError("source_ids must contain at least one source id")
        if any(not source_id.strip() for source_id in source_ids):
            raise ValueError("source_ids must not contain empty source ids")
        return source_ids

    def render_markdown(self) -> str:
        """Render deterministic Markdown for the task complexity assessment."""
        title = get_level_definition(self.required_level).title
        return "\n".join(
            [
                f"# Task Complexity: {self.task_id}",
                "",
                f"**Required level:** {title} (`{self.required_level.value}`)",
                "",
                "## Rationale",
                self.rationale,
                "",
                "## Sources",
                *_render_list(self.source_ids),
            ]
        )


@lru_cache(maxsize=1)
def default_capability_ladder() -> CapabilityLadder:
    """Return the deterministic default Master Blueprint capability ladder."""
    return CapabilityLadder(
        definitions=[
            CapabilityLevelDefinition(
                level=CapabilityLevel.READ_ONLY_AUDIT,
                rank=0,
                title="Read-only Audit",
                description=(
                    "Safely inspect code, tests, logs, and documentation without changing "
                    "repository state."
                ),
                typical_tasks=[
                    "Summarize repository structure",
                    "Trace existing behavior",
                    "Identify likely risk areas",
                ],
                required_evidence=[
                    "Referenced files or artifacts inspected",
                    "Clear summary of observations and limits",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.DOCUMENTATION_BOILERPLATE,
                rank=1,
                title="Documentation Boilerplate",
                description=(
                    "Create or update low-risk documentation and boilerplate without "
                    "changing runtime behavior."
                ),
                typical_tasks=[
                    "Add README sections",
                    "Create template documentation",
                    "Update comments or examples",
                ],
                required_evidence=[
                    "Documentation diff",
                    "Formatting or link check when available",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.SINGLE_FILE_CHANGE,
                rank=2,
                title="Single-file Change",
                description=(
                    "Make a contained behavior or test change in one file with clear local "
                    "verification."
                ),
                typical_tasks=[
                    "Adjust one parser or helper",
                    "Add one focused unit test",
                    "Fix a small validation rule",
                ],
                required_evidence=[
                    "Single-file diff",
                    "Targeted test or compile result",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.LOCALIZED_MULTI_FILE_CHANGE,
                rank=3,
                title="Localized Multi-file Change",
                description=(
                    "Coordinate related edits across a small, well-bounded set of files in "
                    "one local area."
                ),
                typical_tasks=[
                    "Add model plus tests",
                    "Update a module export and caller",
                    "Make paired implementation and fixture changes",
                ],
                required_evidence=[
                    "Bounded file list",
                    "Targeted tests covering touched behavior",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.BOUNDED_DEBUG,
                rank=4,
                title="Bounded Debug",
                description=(
                    "Reproduce, diagnose, and repair a constrained failure with explicit "
                    "before-and-after verification."
                ),
                typical_tasks=[
                    "Fix a failing unit test",
                    "Diagnose a deterministic exception",
                    "Repair a narrow integration regression",
                ],
                required_evidence=[
                    "Failure reproduction",
                    "Root-cause rationale",
                    "Passing targeted verification",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.MODULE_FEATURE_SLICE,
                rank=5,
                title="Module Feature Slice",
                description=(
                    "Deliver a coherent feature slice inside one module or subsystem with "
                    "tests and integration points."
                ),
                typical_tasks=[
                    "Add a new domain model and helpers",
                    "Implement a module-level workflow",
                    "Introduce tested public API surface",
                ],
                required_evidence=[
                    "Feature tests",
                    "Integration or API coverage",
                    "Compile or package check",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.TEACHER_ASSISTED_COMPLEX_REPAIR,
                rank=6,
                title="Teacher-assisted Complex Repair",
                description=(
                    "Perform a complex repair using teacher guidance, preserving a record "
                    "of intervention and verification."
                ),
                typical_tasks=[
                    "Apply teacher-guided architectural fix",
                    "Repair multi-component regression",
                    "Resolve uncertain behavior with escalation",
                ],
                required_evidence=[
                    "Teacher guidance reference",
                    "Repair rationale",
                    "Regression verification",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.IMPLEMENTATION_OPTIONS,
                rank=7,
                title="Implementation Options",
                description=(
                    "Propose and compare multiple viable implementation paths before "
                    "selecting or executing one."
                ),
                typical_tasks=[
                    "Compare architecture options",
                    "Draft migration alternatives",
                    "Analyze trade-offs for a feature approach",
                ],
                required_evidence=[
                    "Options considered",
                    "Trade-off analysis",
                    "Recommendation criteria",
                ],
            ),
            CapabilityLevelDefinition(
                level=CapabilityLevel.TASTE_AWARE_CREATIVE_VARIANTS,
                rank=8,
                title="Taste-aware Creative Variants",
                description=(
                    "Produce differentiated creative variants while respecting project "
                    "taste, constraints, and evaluation criteria."
                ),
                typical_tasks=[
                    "Generate UI copy variants",
                    "Offer design alternatives",
                    "Refine creative direction from preferences",
                ],
                required_evidence=[
                    "Multiple labeled variants",
                    "Taste or preference rationale",
                    "Selection guidance",
                ],
            ),
        ]
    )


def get_level_definition(level: CapabilityLevel | str) -> CapabilityLevelDefinition:
    """Return the default definition for a capability level."""
    normalized = CapabilityLevel(level)
    for definition in default_capability_ladder().definitions:
        if definition.level == normalized:
            return definition
    raise ValueError(f"Unknown capability level: {level}")


def rank_for(level: CapabilityLevel | str) -> int:
    """Return the default rank for a capability level."""
    return get_level_definition(level).rank


def compare_levels(a: CapabilityLevel | str, b: CapabilityLevel | str) -> int:
    """Compare two capability levels by rank."""
    return rank_for(a) - rank_for(b)


def _render_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]
