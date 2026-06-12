from __future__ import annotations

from feiyue_core.curation import CuratorInput
from feiyue_core.workflow import (
    BugDossier,
    LessonPacket,
    ModelRoutingTable,
    RegressionCheck,
    RoleRoute,
    TaskContract,
)


def _task_contract() -> TaskContract:
    return TaskContract(
        task_id="task-123",
        title="Fix flaky parser",
        scope="Make parser deterministic.",
        files_to_modify=["parser.py"],
        requirements=["Preserve public API"],
        acceptance_criteria=["Tests pass"],
        verification_commands=["python -m pytest tests/test_parser.py -q"],
    )


def _bug_dossier() -> BugDossier:
    return BugDossier(
        task_id="task-123",
        original_task="Fix flaky parser",
        changed_files=["parser.py"],
        failing_command="python -m pytest tests/test_parser.py -q",
        error_excerpt="AssertionError: nondeterministic order",
        attempts=["Sorted keys before render"],
        suspected_cause="Hidden unordered set iteration",
        teacher_request="Identify deterministic ordering rule.",
    )


def _lesson_packet() -> LessonPacket:
    return LessonPacket(
        lesson_id="lesson-7",
        project="feiyue",
        trigger="Flaky parser output",
        root_cause="Set iteration leaked into markdown rendering",
        prevention_prompt_rule="Sort unordered collections before rendering.",
        verifier="python -m pytest tests/test_parser.py -q",
        skill_patch_suggestion="Add deterministic render checklist.",
        applies_to=["markdown rendering"],
        source_task_id="task-123",
    )


def test_from_assets_bundles_markdown_and_routing_context() -> None:
    routing_table = ModelRoutingTable.default().model_copy(
        update={"routes": {**ModelRoutingTable.default().routes, "curator": RoleRoute(primary="claude-3.5")}}
    )
    regression_check = RegressionCheck(
        check_id="regression-7",
        description="Guard deterministic parser output",
        command="python -m pytest tests/test_parser.py -q",
        source_lesson_id="lesson-7",
    )

    curator_input = CuratorInput.from_assets(
        input_id="curator-task-123",
        task_contract=_task_contract(),
        bug_dossier=_bug_dossier(),
        teacher_guidance="Prefer the smallest safe fix.",
        verifier_evidence_summary="Targeted pytest passed after sorting.",
        lesson_packet=_lesson_packet(),
        regression_check=regression_check,
        routing_table=routing_table,
        routing_role="curator",
    )

    assert curator_input.source_task_id == "task-123"
    assert curator_input.task_contract_markdown.startswith("# Task Contract: Fix flaky parser")
    assert curator_input.bug_dossier_markdown is not None
    assert curator_input.lesson_packet_markdown is not None
    assert curator_input.regression_check_id == "regression-7"
    assert curator_input.routing_role == "curator"
    assert curator_input.routing_primary == "claude-3.5"

    rendered = curator_input.render_markdown()
    assert rendered == "\n\n".join(
        [
            "# Curator Input: curator-task-123",
            "## Source Task\ntask-123",
            "## Task Contract\n" + curator_input.task_contract_markdown.strip(),
            "## Bug Dossier\n" + curator_input.bug_dossier_markdown.strip(),
            "## Teacher Guidance\nPrefer the smallest safe fix.",
            "## Verifier Evidence Summary\nTargeted pytest passed after sorting.",
            "## Lesson Packet\n" + curator_input.lesson_packet_markdown.strip(),
            "## Regression Check\n- ID: regression-7",
            "## Routing Context\n- Role: curator\n- Primary: claude-3.5",
        ]
    ) + "\n"


def test_optional_sections_render_none() -> None:
    curator_input = CuratorInput.from_assets(
        input_id="curator-minimal",
        task_contract=_task_contract(),
    )

    rendered = curator_input.render_markdown()

    assert curator_input.source_task_id == "task-123"
    assert "## Bug Dossier\n- None" in rendered
    assert "## Teacher Guidance\n- None" in rendered
    assert "## Verifier Evidence Summary\n- None" in rendered
    assert "## Lesson Packet\n- None" in rendered
    assert "## Regression Check\n- None" in rendered
    assert "## Routing Context\n- None" in rendered


def test_guidance_and_verifier_evidence_are_truncated_with_clear_marker() -> None:
    curator_input = CuratorInput.from_assets(
        input_id="curator-truncated",
        task_contract=_task_contract(),
        teacher_guidance="abcdef",
        verifier_evidence_summary="uvwxyz",
        max_teacher_guidance_chars=3,
        max_verifier_evidence_chars=4,
    )

    assert curator_input.teacher_guidance == "abc... [truncated 3 chars]"
    assert curator_input.verifier_evidence_summary == "uvwx... [truncated 2 chars]"


def test_unknown_routing_role_records_role_without_primary() -> None:
    curator_input = CuratorInput.from_assets(
        input_id="curator-route-missing",
        task_contract=_task_contract(),
        routing_table=ModelRoutingTable.default(),
        routing_role="nonexistent",
    )

    assert curator_input.routing_role == "nonexistent"
    assert curator_input.routing_primary is None
    assert "## Routing Context\n- Role: nonexistent\n- Primary: None" in curator_input.render_markdown()
