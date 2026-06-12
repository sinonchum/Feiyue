from __future__ import annotations

from feiyue_core.workflow import (
    BugDossier,
    LessonPacket,
    ModelRoutingTableInitializer,
    ModelRoutingTableLoader,
    ProjectKnowledgeInitializer,
    RegressionEvalWriter,
    build_regression_check_from_lesson,
    build_task_contract,
    build_worker_context,
)


def test_workflow_assets_connect_project_context_task_contract_lessons_evals_and_routing(tmp_path) -> None:
    ProjectKnowledgeInitializer(tmp_path).initialize()
    routing_path = ModelRoutingTableInitializer(tmp_path).initialize()
    hermes_dir = tmp_path / ".hermes"
    (hermes_dir / "project-memory.md").write_text("Project uses strict i18n from day one.\n", encoding="utf-8")
    (hermes_dir / "rules.md").write_text("Worker must not expand scope.\n", encoding="utf-8")
    (hermes_dir / "design-laws.md").write_text("No gradients, neon, or warm yellow.\n", encoding="utf-8")
    (hermes_dir / "architecture.md").write_text("Workflow assets live under .hermes/.\n", encoding="utf-8")

    routing_table = ModelRoutingTableLoader(tmp_path).load()
    assert routing_path == hermes_dir / "model-routing.yaml"
    assert routing_table.routes["worker"].primary == "default"
    assert routing_table.routes["teacher_debug"].primary == "default"

    worker_context = build_worker_context(tmp_path)
    contract = build_task_contract(
        task_id="m5-demo-task",
        title="Add project workflow context",
        scope="Render project knowledge into a worker-safe task contract.",
        files_to_modify=["packages/feiyue-core/feiyue_core/workflow/project_knowledge.py"],
        files_not_to_touch=["README.md"],
        context=[worker_context, f"Worker route: {routing_table.routes['worker'].primary}"],
        requirements=["Render deterministic Markdown", "Do not call providers"],
        acceptance_criteria=["Targeted workflow tests pass"],
        verification_commands=["python -m pytest tests/test_workflow_assets_integration.py -q"],
        escalation_rule="If tests fail twice, create a bug dossier for teacher review.",
    )

    rendered_contract = contract.render_markdown()
    assert "# Task Contract: Add project workflow context" in rendered_contract
    assert "Project uses strict i18n from day one." in rendered_contract
    assert "Worker must not expand scope." in rendered_contract
    assert "No gradients, neon, or warm yellow." in rendered_contract
    assert "Worker route: default" in rendered_contract

    dossier = BugDossier(
        task_id=contract.task_id,
        original_task=rendered_contract,
        changed_files=contract.files_to_modify,
        failing_command="python -m pytest tests/test_workflow_assets_integration.py -q",
        error_excerpt="AssertionError: missing deterministic section",
        attempts=["Added renderer", "Re-ran targeted test"],
        suspected_cause="Task contract omitted required project context section.",
        teacher_request="Diagnose the minimal template fix and prevention rule.",
    )
    rendered_dossier = dossier.render_markdown()
    assert "# Bug Dossier" in rendered_dossier
    assert "m5-demo-task" in rendered_dossier
    assert "Request to Teacher" in rendered_dossier

    lesson = LessonPacket(
        lesson_id="workflow-context-required",
        project="Feiyue",
        trigger="Worker task contract omitted project context.",
        root_cause="Task template did not require project knowledge injection.",
        prevention_prompt_rule="Always include Project Knowledge Context before worker requirements.",
        verifier="python -m pytest tests/test_workflow_assets_integration.py -q",
        skill_patch_suggestion="Patch task template generation to include project knowledge context.",
        applies_to=["task-contract", "worker-context", "m5"],
        source_task_id=contract.task_id,
    )
    rendered_lesson = lesson.render_markdown()
    assert "# Lesson Packet: workflow-context-required" in rendered_lesson
    assert "Always include Project Knowledge Context" in rendered_lesson
    assert "- task-contract" in rendered_lesson

    check = build_regression_check_from_lesson(lesson)
    assets = RegressionEvalWriter(tmp_path).write([check])
    forbidden_patterns = assets.forbidden_patterns_path.read_text(encoding="utf-8")
    regression_script = assets.regression_checks_path.read_text(encoding="utf-8")

    assert assets.forbidden_patterns_path == hermes_dir / "evals" / "forbidden-patterns.txt"
    assert assets.regression_checks_path == hermes_dir / "evals" / "regression-checks.sh"
    assert "workflow-context-required" in forbidden_patterns
    assert "command: python -m pytest tests/test_workflow_assets_integration.py -q" in forbidden_patterns
    assert regression_script.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "python -m pytest tests/test_workflow_assets_integration.py -q" in regression_script
