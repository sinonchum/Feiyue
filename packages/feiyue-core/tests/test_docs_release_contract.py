from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "README.md"
RELEASE_CHECKLIST = REPO_ROOT / "docs" / "release-checklist.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
DOCS_INDEX = REPO_ROOT / "docs" / "index.md"
REAL_PROVIDER_PLAN = REPO_ROOT / "docs" / "real-provider-integration-plan.md"
ARCHITECTURE_DIAGRAM = REPO_ROOT / "docs" / "assets" / "feiyue-architecture.svg"
OUTLINE = REPO_ROOT / "docs" / "Feiyue-self-evolution-development-outline.md"
PRD = REPO_ROOT / "docs" / "Feiyue-PRD.md"
SYSTEM_DOCTRINE = REPO_ROOT / "docs" / "Feiyue-system-doctrine.md"
DEVELOPMENT_OUTLINE = REPO_ROOT / "docs" / "Feiyue-development-outline.md"


def test_readme_indexes_release_contribution_and_architecture_docs() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "docs/release-checklist.md" in readme
    assert "CONTRIBUTING.md" in readme
    assert "docs/architecture.md" in readme
    assert "docs/index.md" in readme
    assert "docs/assets/feiyue-architecture.svg" in readme


def test_docs_index_links_canonical_docs_and_provider_free_surfaces() -> None:
    content = DOCS_INDEX.read_text(encoding="utf-8")

    assert "# Feiyue Docs" in content
    assert "Feiyue-master-blueprint.md" in content
    assert "Feiyue-system-doctrine.md" in content
    assert "architecture.md" in content
    assert "assets/feiyue-architecture.svg" in content
    assert "release-checklist.md" in content
    assert "real-provider-integration-plan.md" in content
    assert "../CONTRIBUTING.md" in content
    assert "provider-free example smoke" in content
    assert "provider-free benchmark smoke" in content


def test_release_checklist_captures_m14_gates_and_authorization_boundaries() -> None:
    content = RELEASE_CHECKLIST.read_text(encoding="utf-8")

    assert "# Feiyue Release Checklist" in content
    assert "python -m compileall -q feiyue_core" in content
    assert "python -m pytest -q" in content
    assert "PROVIDER_FREE_EXAMPLE_SMOKE_OK" in content
    assert "BENCHMARK_SMOKE_OK" in content
    assert "STATIC_EXPORT_ALL_OK" in content
    assert "SECRET_SCAN_OK" in content
    assert "Real provider execution requires explicit authorization" in content
    assert "docs/real-provider-integration-plan.md" in content
    assert "Hermes config mutation is out of scope" in content
    assert "Current baseline: 523 passed" in content


def test_real_provider_integration_plan_exists_and_defines_authorized_sequence() -> None:
    content = REAL_PROVIDER_PLAN.read_text(encoding="utf-8")

    assert "# Real Provider Integration Plan" in content
    assert "real provider execution" in content
    assert "Hermes profile subprocess" in content
    assert "real HTTP smoke" in content
    assert "teacher escalation" in content
    assert "real weak/strong benchmark" in content
    assert "explicit human authorization" in content
    assert "provider-free fake tests" in content
    assert "redaction/diagnostics" in content
    assert "isolated dry-run/smoke" in content
    assert "no global Hermes config mutation" in content
    assert "auditable run evidence" in content
    assert "rollback/abort gates" in content
    assert "Authorization Checklist" in content
    assert "Forbidden Actions" in content
    assert "Do not read, print, copy, or commit real credentials" in content
    assert "Do not implement real provider calls in this documentation lane" in content


def test_contributing_guide_documents_tdd_provider_free_and_secret_rules() -> None:
    content = CONTRIBUTING.read_text(encoding="utf-8")

    assert "# Contributing to Feiyue" in content
    assert "RED-GREEN-REFACTOR" in content
    assert "provider-free by default" in content
    assert "No real provider credentials" in content
    assert "Do not mutate Hermes configuration" in content
    assert "Terminal: `\"python -m pytest -q\"`" in content


def test_architecture_doc_explains_provider_free_flow_and_handoff_surfaces() -> None:
    content = ARCHITECTURE.read_text(encoding="utf-8")

    assert "# Feiyue Architecture" in content
    assert "Human Creative Direction" in content
    assert "Strong Spec / Teacher" in content
    assert "Weak Worker / Student" in content
    assert "Verifier" in content
    assert "Run Evidence" in content
    assert "Static Export Bundle" in content
    assert "Policy Governor" in content
    assert "Provider-Free Foundation" in content
    assert "assets/feiyue-architecture.svg" in content


def test_architecture_svg_is_static_provider_free_and_has_core_role_labels() -> None:
    content = ARCHITECTURE_DIAGRAM.read_text(encoding="utf-8")

    assert "<svg" in content
    assert "Human Creative Direction" in content
    assert "Strong Spec / Teacher" in content
    assert "Task Contract" in content
    assert "Weak Worker / Student" in content
    assert "Sandbox / Candidate Writes" in content
    assert "Verifier" in content
    assert "Policy Governor" in content
    assert "Run Evidence" in content
    assert "Handoff / Dashboard / Static Export Bundle" in content
    assert "Curator / Asset Promotion" in content
    assert "<script" not in content.lower()
    assert "cdn" not in content.lower()
    assert "<image" not in content.lower()
    assert "href=\"http" not in content.lower()
    assert "src=\"http" not in content.lower()
    assert "href=" not in content.lower()


def test_outline_marks_docs_release_checklist_slice_done() -> None:
    content = OUTLINE.read_text(encoding="utf-8")

    assert "M14 Docs / Release Checklist Skeleton" in content
    assert "docs/release-checklist.md" in content
    assert "CONTRIBUTING.md" in content
    assert "docs/architecture.md" in content


def test_canonical_docs_use_gemini_31_pro_for_strong_model_examples() -> None:
    for path in (PRD, SYSTEM_DOCTRINE, DEVELOPMENT_OUTLINE):
        content = path.read_text(encoding="utf-8")
        assert "Gemini 3.1 Pro" in content
        assert "Gemini 2.5 Pro" not in content
        assert "gemini-2.5-pro" not in content.lower()


def test_status_docs_capture_wave4_real_profile_benchmark_checkpoint() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `523 passed`" in content
        assert "Wave4-1F" in content
        assert "45/45 real Hermes profile calls" in content
        assert "gemini-3.1-pro" in content
        assert "M10 real profile benchmark lane usable" in content
        assert "M10 real multi-worker execution lane not yet implemented" in content


def test_status_docs_capture_wave4_2b_real_profile_workflow_smoke() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `523 passed`" in content
        assert "Wave4-2B" in content
        assert "WAVE4_2B_REAL_PROFILE_WORKFLOW_OK" in content
        assert "feiyue-weak-deepseek-flash" in content
        assert "provider_call_count: 1" in content
        assert "workflow_status: verified" in content


def test_status_docs_capture_wave4_2c_real_teacher_retry_smoke() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `523 passed`" in content
        assert "Wave4-2C" in content
        assert "WAVE4_2C_REAL_TEACHER_RETRY_OK" in content
        assert "feiyue-strong-gpt55" in content
        assert "provider_call_count: 3" in content
        assert "initial_workflow_status: needs_teacher" in content
        assert "final_workflow_status: verified" in content


def test_status_docs_capture_wave4_2d_and_wave4_3a_productized_runner() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `523 passed`" in content
        assert "Wave4-2D" in content
        assert "RealProfileWorkflowRunner" in content
        assert "feiyue-runs workflow-smoke" in content
        assert "Wave4-3A" in content
        assert "dry_run_only: true" in content
        assert "promotion_attempted: false" in content


def test_status_docs_capture_wave4_3b_approval_gate() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `523 passed`" in content
        assert "Wave4-3B-1" in content
        assert "RealProfilePromotionApproval" in content
        assert "Wave4-3B-2" in content
        assert "RealProfilePromotionGate" in content
        assert "feiyue-runs workflow-promotion" in content
        assert "missing_promotion_approval" in content
        assert "promotion_approval_applies" in content


def test_status_docs_capture_wave4_3b_real_project_promotion_smoke() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Wave4-3B-3" in content
        assert "wave4-3b-3-low-risk-real-project-promotion-smoke-v3" in content
        assert "feiyue/w43b-approved-promotion-smoke" in content
        assert "66f6055fec5a90f192b78bc6719e6938d46ba053" in content


def test_status_docs_capture_wave4_3c_productized_approval_cli() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Wave4-3C" in content
        assert "approve-promotion" in content
        assert "promote-approved" in content
        assert "wave4-3c-productized-approval-cli-smoke-v2" in content
        assert "feiyue/w43c-productized-approval-cli-smoke" in content
        assert "d8370868a992320590d23865b2e77099b57930ad" in content


def test_status_docs_capture_wave4_4_capability_feedback_loop() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Wave4-4" in content
        assert "capability-feedback" in content
        assert "CapabilityFeedbackAggregator" in content
        assert "routing_table_mutated: false" in content
        assert "latest.json" in content
        assert "latest.md" in content


def test_status_docs_capture_wave4_4b_routing_proposal() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Wave4-4B" in content
        assert "RoutingProposalGenerator" in content
        assert "feiyue-runs routing-proposal" in content
        assert "wave4-4b-routing-proposal-smoke" in content
        assert "requires_human_approval" in content
        assert "routing_table_mutated: false" in content


def test_status_docs_capture_wave4_4c_approval_gated_routing_apply() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Wave4-4C" in content
        assert "RoutingApplyGate" in content
        assert "approve-routing-proposal" in content
        assert "apply-approved-routing" in content
        assert "wave4-4c-routing-apply-smoke" in content
        assert "routing_proposal_approval_applies" in content


def test_status_docs_capture_wave4_5_multi_worker_orchestration_hardening() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `523 passed`" in content
        assert "Wave4-5" in content
        assert "MultiWorkerOrchestrationPlanner" in content
        assert "feiyue-runs multi-worker-plan" in content
        assert "wave4-5-multi-worker-orchestration-smoke" in content
        assert "routing_apply_evidence_loaded" in content
        assert "provider_execution_requested: false" in content
        assert "global_hermes_config_mutated: false" in content


def test_status_docs_capture_wave4_5b_multi_worker_workflow_dry_run() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `523 passed`" in content
        assert "Wave4-5B" in content
        assert "MultiWorkerWorkflowDryRunOrchestrator" in content
        assert "feiyue-runs multi-worker-workflow" in content
        assert "wave4-5b-approved-multi-worker-dry-run-smoke" in content
        assert "multi_worker_plan_authorization_applies" in content
        assert "dry_run_only: true" in content
        assert "promotion_attempted: false" in content
        assert "global_hermes_config_mutated: false" in content
