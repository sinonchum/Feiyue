from __future__ import annotations

from feiyue_core.curation import (
    CuratorInput,
    ProposalPatch,
    ProposalStatus,
    ReviewDecisionStatus,
    ReviewGate,
    build_distillation_proposal,
    normalize_teacher_guidance,
)
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


def test_curation_connects_workflow_assets_to_reviewed_distillation_decision(tmp_path) -> None:
    ProjectKnowledgeInitializer(tmp_path).initialize()
    ModelRoutingTableInitializer(tmp_path).initialize()
    hermes_dir = tmp_path / ".hermes"
    (hermes_dir / "project-memory.md").write_text("Project uses strict i18n from day one.\n", encoding="utf-8")
    (hermes_dir / "rules.md").write_text("Worker must not expand scope.\n", encoding="utf-8")
    (hermes_dir / "design-laws.md").write_text("No gradients, neon, or warm yellow.\n", encoding="utf-8")
    (hermes_dir / "architecture.md").write_text("Workflow assets live under .hermes/.\n", encoding="utf-8")

    routing_table = ModelRoutingTableLoader(tmp_path).load()
    worker_context = build_worker_context(tmp_path)
    contract = build_task_contract(
        task_id="m6-demo-task",
        title="Distill workflow failure",
        scope="Turn workflow failure evidence into review-required curation proposals.",
        files_to_modify=["packages/feiyue-core/feiyue_core/curation/curator_input.py"],
        files_not_to_touch=["README.md"],
        context=[worker_context, f"Curator route: {routing_table.routes['curator'].primary}"],
        requirements=["Bundle evidence deterministically", "Do not auto-approve proposals"],
        acceptance_criteria=["Curation integration smoke passes"],
        verification_commands=["python -m pytest tests/test_curation_integration.py -q"],
        escalation_rule="If evidence is too long, truncate with a clear marker.",
    )
    dossier = BugDossier(
        task_id=contract.task_id,
        original_task=contract.render_markdown(),
        changed_files=contract.files_to_modify,
        failing_command="python -m pytest tests/test_curation_integration.py -q",
        error_excerpt="AssertionError: proposal was auto-approved",
        attempts=["Added review_required status", "Re-ran targeted test"],
        suspected_cause="Distillation proposal skipped human review gate.",
        teacher_request="Identify the minimal review-first proposal rule.",
    )
    lesson = LessonPacket(
        lesson_id="proposal-review-required",
        project="Feiyue",
        trigger="Distillation proposal was auto-approved.",
        root_cause="Curation layer did not force review-required status.",
        prevention_prompt_rule="Every distillation proposal must start as review_required.",
        verifier="python -m pytest tests/test_curation_integration.py -q",
        skill_patch_suggestion="Add review-first curation checklist.",
        applies_to=["curation", "distillation", "review-gate"],
        source_task_id=contract.task_id,
    )
    regression_check = build_regression_check_from_lesson(lesson)
    RegressionEvalWriter(tmp_path).write([regression_check])

    raw_teacher_guidance = "\n".join(
        [
            "Root Cause: Distillation proposal skipped the human review gate.",
            "Minimal Fix Strategy: Keep proposals review_required and create a separate review decision.",
            "Prevention Rule: Never promote curation assets without explicit reviewer action.",
            "Suggested Asset Updates:",
            "- lesson",
            "- regression_eval",
            "- routing_rule",
        ]
    )
    guidance_summary = normalize_teacher_guidance(
        guidance_id="teacher-guidance-m6-demo-task",
        source_task_id=contract.task_id,
        raw_guidance=raw_teacher_guidance,
        source_ids=[contract.task_id, dossier.task_id],
    )
    assert guidance_summary.root_cause == "Distillation proposal skipped the human review gate."
    assert guidance_summary.minimal_fix_strategy == (
        "Keep proposals review_required and create a separate review decision."
    )
    assert guidance_summary.prevention_rule == (
        "Never promote curation assets without explicit reviewer action."
    )
    assert guidance_summary.suggested_asset_updates == ["lesson", "regression_eval", "routing_rule"]

    curator_input = CuratorInput.from_assets(
        input_id="curator-m6-demo-task",
        task_contract=contract,
        bug_dossier=dossier,
        teacher_guidance=guidance_summary.render_markdown(),
        verifier_evidence_summary="Targeted curation integration test failed until status defaulted to review_required.",
        lesson_packet=lesson,
        regression_check=regression_check,
        routing_table=routing_table,
        routing_role="curator",
    )
    rendered_curator_input = curator_input.render_markdown()
    assert "# Curator Input: curator-m6-demo-task" in rendered_curator_input
    assert "## Routing Context\n- Role: curator\n- Primary: default" in rendered_curator_input
    assert "Teacher Guidance Summary: teacher-guidance-m6-demo-task" in rendered_curator_input

    proposal = build_distillation_proposal(
        proposal_id="distill-m6-demo-task",
        source_task_id=contract.task_id,
        source_input_id=curator_input.input_id,
        patches=[
            ProposalPatch(
                asset_type="lesson",
                target_path=".hermes/lessons/proposal-review-required.md",
                summary="Persist the review-required curation lesson.",
                proposed_content=lesson.render_markdown(),
                source_ids=[curator_input.input_id, lesson.lesson_id, guidance_summary.guidance_id],
            ),
            ProposalPatch(
                asset_type="regression_eval",
                target_path=".hermes/evals/regression-checks.sh",
                summary="Add a curation review-gate regression check.",
                proposed_content=regression_check.command,
                source_ids=[curator_input.input_id, regression_check.check_id, guidance_summary.guidance_id],
            ),
            ProposalPatch(
                asset_type="routing_rule",
                target_path=".hermes/model-routing.yaml",
                summary="Keep curator routing explicit before using real providers.",
                proposed_content=routing_table.render_yaml(),
                source_ids=[curator_input.input_id, "curator", guidance_summary.guidance_id],
            ),
        ],
    )
    rendered_proposal = proposal.render_markdown()

    assert proposal.status is ProposalStatus.REVIEW_REQUIRED
    assert "# Distillation Proposal: distill-m6-demo-task" in rendered_proposal
    assert "## Status\n\nreview_required" in rendered_proposal
    assert "teacher-guidance-m6-demo-task" in rendered_proposal
    assert "## Status\n\napproved" not in rendered_proposal

    review_decision = ReviewGate().accept(
        proposal,
        decision_id="review-m6-demo-task",
        reviewer_id="human-reviewer",
        rationale="Accept the review-first curation lesson because it prevents automatic asset promotion.",
    )
    rendered_decision = review_decision.render_markdown()

    assert review_decision.decision is ReviewDecisionStatus.ACCEPTED
    assert review_decision.source_ids == [proposal.proposal_id, proposal.source_input_id, proposal.source_task_id]
    assert "# Review Decision: review-m6-demo-task" in rendered_decision
    assert "## Decision\n\naccepted" in rendered_decision
    assert "human-reviewer" in rendered_decision
