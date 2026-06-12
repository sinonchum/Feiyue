from __future__ import annotations

from pydantic import ValidationError

from feiyue_core.capability.ladder import (
    CapabilityLadder,
    CapabilityLevel,
    CapabilityLevelDefinition,
    TaskComplexity,
    compare_levels,
    default_capability_ladder,
    get_level_definition,
    rank_for,
)

EXPECTED_LEVEL_VALUES = [
    "read_only_audit",
    "documentation_boilerplate",
    "single_file_change",
    "localized_multi_file_change",
    "bounded_debug",
    "module_feature_slice",
    "teacher_assisted_complex_repair",
    "implementation_options",
    "taste_aware_creative_variants",
]


def test_capability_level_values_match_blueprint_order() -> None:
    assert [level.value for level in CapabilityLevel] == EXPECTED_LEVEL_VALUES


def test_default_capability_ladder_is_deterministically_ordered() -> None:
    ladder = default_capability_ladder()

    assert [definition.level.value for definition in ladder.definitions] == EXPECTED_LEVEL_VALUES
    assert [definition.rank for definition in ladder.definitions] == list(
        range(len(EXPECTED_LEVEL_VALUES))
    )
    assert ladder.render_markdown() == default_capability_ladder().render_markdown()
    assert ladder.render_markdown().splitlines()[:6] == [
        "# Capability Ladder",
        "",
        "## 0. Read-only Audit (`read_only_audit`)",
        "Safely inspect code, tests, logs, and documentation without changing repository state.",
        "",
        "**Typical tasks:**",
    ]


def test_ladder_rejects_duplicate_levels() -> None:
    definition = CapabilityLevelDefinition(
        level=CapabilityLevel.READ_ONLY_AUDIT,
        rank=0,
        title="Read-only Audit",
        description="Inspect only.",
        typical_tasks=["Read a file"],
        required_evidence=["Notes"],
    )

    try:
        CapabilityLadder(definitions=[definition, definition.model_copy(update={"rank": 1})])
    except ValidationError:
        pass
    else:
        raise AssertionError("CapabilityLadder should reject duplicate levels")


def test_ladder_rejects_non_contiguous_ranks_starting_at_zero() -> None:
    definitions = [
        CapabilityLevelDefinition(
            level=CapabilityLevel.READ_ONLY_AUDIT,
            rank=0,
            title="Read-only Audit",
            description="Inspect only.",
            typical_tasks=["Read a file"],
            required_evidence=["Notes"],
        ),
        CapabilityLevelDefinition(
            level=CapabilityLevel.DOCUMENTATION_BOILERPLATE,
            rank=2,
            title="Documentation Boilerplate",
            description="Create docs.",
            typical_tasks=["Write README"],
            required_evidence=["Diff"],
        ),
    ]

    try:
        CapabilityLadder(definitions=definitions)
    except ValidationError:
        pass
    else:
        raise AssertionError("CapabilityLadder should reject non-contiguous ranks")


def test_level_lookup_and_comparison_helpers() -> None:
    assert rank_for(CapabilityLevel.READ_ONLY_AUDIT) == 0
    assert rank_for("bounded_debug") == 4
    assert get_level_definition("single_file_change").title == "Single-file Change"
    assert compare_levels(
        CapabilityLevel.READ_ONLY_AUDIT, CapabilityLevel.BOUNDED_DEBUG
    ) < 0
    assert compare_levels("module_feature_slice", "module_feature_slice") == 0
    assert compare_levels("taste_aware_creative_variants", "implementation_options") > 0


def test_task_complexity_validates_sources_and_renders_markdown() -> None:
    complexity = TaskComplexity(
        task_id="task-123",
        required_level=CapabilityLevel.BOUNDED_DEBUG,
        rationale="Requires reproducing and fixing a constrained failing behavior.",
        source_ids=["issue-7", "trace-2"],
    )

    assert complexity.render_markdown() == "\n".join(
        [
            "# Task Complexity: task-123",
            "",
            "**Required level:** Bounded Debug (`bounded_debug`)",
            "",
            "## Rationale",
            "Requires reproducing and fixing a constrained failing behavior.",
            "",
            "## Sources",
            "- issue-7",
            "- trace-2",
        ]
    )

    for source_ids in ([], ["issue-7", ""], ["   "]):
        try:
            TaskComplexity(
                task_id="task-invalid",
                required_level=CapabilityLevel.READ_ONLY_AUDIT,
                rationale="Missing valid source evidence.",
                source_ids=source_ids,
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("TaskComplexity should reject empty source ids")
