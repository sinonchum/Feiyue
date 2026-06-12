from __future__ import annotations

from pydantic import ValidationError

from feiyue_core.workflow.lesson_packet import LessonPacket


def test_lesson_packet_renders_deterministic_markdown() -> None:
    packet = LessonPacket(
        lesson_id="lesson-001",
        project="feiyue-core",
        trigger="Repeated pytest failure after candidate patch.",
        root_cause="Candidate changed public behavior without updating verifier expectations.",
        prevention_prompt_rule="Before editing behavior, identify all verifier assumptions.",
        verifier="python -m pytest -q",
        skill_patch_suggestion="Add a checklist item for verifier-contract review.",
        applies_to=["pytest verifiers", "candidate review"],
        source_task_id="task-123",
    )

    assert packet.render_markdown() == "\n".join(
        [
            "# Lesson Packet: lesson-001",
            "",
            "## Project",
            "feiyue-core",
            "",
            "## Trigger",
            "Repeated pytest failure after candidate patch.",
            "",
            "## Root Cause",
            "Candidate changed public behavior without updating verifier expectations.",
            "",
            "## Prevention",
            "**Prompt Rule:** Before editing behavior, identify all verifier assumptions.",
            "",
            "**Verifier:** `python -m pytest -q`",
            "",
            "**Skill Patch Suggestion:** Add a checklist item for verifier-contract review.",
            "",
            "## Applies To",
            "- pytest verifiers",
            "- candidate review",
            "",
            "## Source Task",
            "task-123",
        ]
    )


def test_lesson_packet_empty_applies_to_renders_none() -> None:
    packet = LessonPacket(
        lesson_id="lesson-empty",
        project="feiyue-core",
        trigger="Teacher intervention requested.",
        root_cause="Missing prior lesson.",
        prevention_prompt_rule="Check existing lessons first.",
        verifier="python -m pytest -q",
        skill_patch_suggestion="Document the check.",
        applies_to=[],
        source_task_id="task-empty",
    )

    assert "## Applies To\n- None" in packet.render_markdown()


def test_lesson_packet_rejects_unknown_fields() -> None:
    try:
        LessonPacket(
            lesson_id="lesson-001",
            project="feiyue-core",
            trigger="Failure.",
            root_cause="Unknown.",
            prevention_prompt_rule="Ask teacher.",
            verifier="pytest",
            skill_patch_suggestion="Patch skill.",
            applies_to=[],
            source_task_id="task-123",
            unexpected=True,
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("LessonPacket should reject unknown fields")
