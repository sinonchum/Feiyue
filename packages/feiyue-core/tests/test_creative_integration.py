from __future__ import annotations

from feiyue_core.capability import CapabilityLevel, default_capability_ladder, rank_for
from feiyue_core.creative import (
    CreativeBrief,
    CreativeCritique,
    CreativeCritiqueRecommendation,
    CreativeVariant,
    CreativeVariantType,
    UserSelectionFeedback,
    UserSelectionStatus,
)
from feiyue_core.workflow import ProjectKnowledgeInitializer, build_worker_context


def test_creative_brief_variants_critique_and_selection_are_candidate_evidence(tmp_path) -> None:
    ProjectKnowledgeInitializer(tmp_path).initialize()
    hermes_dir = tmp_path / ".hermes"
    (hermes_dir / "project-memory.md").write_text(
        "Feiyue turns creative direction into verified workflow assets.\n",
        encoding="utf-8",
    )
    (hermes_dir / "rules.md").write_text(
        "Creative output must stay candidate-only until user selection.\n",
        encoding="utf-8",
    )
    (hermes_dir / "design-laws.md").write_text(
        "No gradients, neon, or warm yellow.\n",
        encoding="utf-8",
    )
    (hermes_dir / "architecture.md").write_text(
        "Creative role depends on project knowledge and capability boundaries.\n",
        encoding="utf-8",
    )

    worker_context = build_worker_context(tmp_path)
    ladder = default_capability_ladder()
    assert rank_for(CapabilityLevel.IMPLEMENTATION_OPTIONS) < rank_for(
        CapabilityLevel.TASTE_AWARE_CREATIVE_VARIANTS
    )
    assert "Taste-aware Creative Variants" in ladder.render_markdown()

    brief = CreativeBrief.from_project_knowledge(
        brief_id="creative-brief-m8-demo",
        human_seed="Help Feiyue propose safer next-step product ideas from accumulated lessons.",
        project_knowledge_markdown=worker_context,
        design_laws=["No gradients, neon, or warm yellow."],
        non_goals=["Do not turn a creative candidate into a task without user selection."],
        constraints=["Provider-free first slice", "Candidate-only artifacts"],
        target_users=["Human creative director", "Weak-model worker orchestrator"],
        desired_outcomes=["Useful creative variants with explicit verification ideas"],
        source_ids=["project-knowledge-m8-demo", "master-blueprint-outcome-c"],
    )
    rendered_brief = brief.render_markdown()
    assert "# Creative Brief: creative-brief-m8-demo" in rendered_brief
    assert "Candidate-only artifacts" in rendered_brief
    assert "master-blueprint-outcome-c" in rendered_brief

    variants = [
        CreativeVariant(
            variant_id="variant-conservative-m8-demo",
            brief_id=brief.brief_id,
            variant_type=CreativeVariantType.CONSERVATIVE,
            pitch="Add a reviewed opportunity list generated from accepted lesson packets.",
            rationale="This keeps creative work close to verified project evidence.",
            risks=["May be too incremental"],
            non_goals=["No automatic PRD creation"],
            verification_idea="User can accept or reject each opportunity candidate.",
            required_capability_level=CapabilityLevel.IMPLEMENTATION_OPTIONS.value,
            source_ids=[brief.brief_id, "lesson-corpus"],
        ),
        CreativeVariant(
            variant_id="variant-bold-m8-demo",
            brief_id=brief.brief_id,
            variant_type=CreativeVariantType.BOLD,
            pitch="Let the creative role propose cross-project transfer ideas from recurring failures.",
            rationale="This pushes Feiyue toward taste-aware opportunity discovery.",
            risks=["Could overfit noisy lessons", "Needs strict user review"],
            non_goals=["No bypassing user final selection"],
            verification_idea="Track accepted creative proposal rate and rejected violation rate.",
            required_capability_level=CapabilityLevel.TASTE_AWARE_CREATIVE_VARIANTS.value,
            source_ids=[brief.brief_id, "master-blueprint-outcome-c"],
        ),
    ]

    for variant in variants:
        rendered_variant = variant.render_markdown()
        assert "- Candidate Only: true" in rendered_variant
        assert variant.brief_id == brief.brief_id
        assert variant.candidate_only is True
        assert "## Verification Idea" in rendered_variant

    critique = CreativeCritique(
        critique_id="critique-bold-m8-demo",
        variant_id=variants[1].variant_id,
        constraint_violations=[],
        risk_assessment="Bold cross-project transfer may overfit noisy lessons.",
        feasibility_notes="Feasible as a candidate review artifact before any PRD conversion.",
        verification_cost="Medium: requires user review and accepted proposal metrics.",
        recommendation=CreativeCritiqueRecommendation.REVISE,
        source_ids=[brief.brief_id, variants[1].variant_id, "design-laws-m8-demo"],
    )
    rendered_critique = critique.render_markdown()
    assert "# Creative Critique: critique-bold-m8-demo" in rendered_critique
    assert "- Recommendation: revise" in rendered_critique
    assert "## Constraint Violations\n\n- None" in rendered_critique

    feedback = UserSelectionFeedback(
        feedback_id="selection-m8-demo",
        brief_id=brief.brief_id,
        selected_variant_id=variants[0].variant_id,
        status=UserSelectionStatus.ACCEPTED,
        rationale="The conservative variant is useful because it stays grounded in reviewed lessons.",
        violated_design_laws=[],
        useful_aspects=["grounded in lessons", "clear verification path"],
        source_ids=[brief.brief_id, variants[0].variant_id, critique.critique_id],
    )
    rendered_feedback = feedback.render_markdown()

    assert feedback.status is UserSelectionStatus.ACCEPTED
    assert feedback.selected_variant_id == "variant-conservative-m8-demo"
    assert "# User Selection Feedback: selection-m8-demo" in rendered_feedback
    assert "- Status: accepted" in rendered_feedback
    assert "grounded in lessons" in rendered_feedback
