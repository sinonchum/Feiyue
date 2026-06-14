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
CLI_REFERENCE = REPO_ROOT / "docs" / "cli-reference.md"
OUTLINE = REPO_ROOT / "docs" / "Feiyue-self-evolution-development-outline.md"
PRD = REPO_ROOT / "docs" / "Feiyue-PRD.md"
SYSTEM_DOCTRINE = REPO_ROOT / "docs" / "Feiyue-system-doctrine.md"
DEVELOPMENT_OUTLINE = REPO_ROOT / "docs" / "Feiyue-development-outline.md"
OPERATOR_GUIDE = REPO_ROOT / "docs" / "operator-guide.md"
APPROVAL_RUNBOOKS = REPO_ROOT / "docs" / "approval-runbooks.md"
LIVE_SMOKE_PLAYBOOK = REPO_ROOT / "docs" / "live-smoke-playbook.md"
SECURITY_BOUNDARIES = REPO_ROOT / "docs" / "security-boundaries.md"
ROLLBACK_GUIDE = REPO_ROOT / "docs" / "rollback-guide.md"
OPERATOR_DOCS = (
    OPERATOR_GUIDE,
    APPROVAL_RUNBOOKS,
    LIVE_SMOKE_PLAYBOOK,
    SECURITY_BOUNDARIES,
    ROLLBACK_GUIDE,
)


def test_readme_indexes_release_contribution_and_architecture_docs() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "docs/release-checklist.md" in readme
    assert "CONTRIBUTING.md" in readme
    assert "docs/architecture.md" in readme
    assert "docs/index.md" in readme
    assert "docs/cli-reference.md" in readme
    assert "docs/assets/feiyue-architecture.svg" in readme


def test_docs_index_links_canonical_docs_and_provider_free_surfaces() -> None:
    content = DOCS_INDEX.read_text(encoding="utf-8")

    assert "# Feiyue Docs" in content
    assert "Feiyue-master-blueprint.md" in content
    assert "Feiyue-system-doctrine.md" in content
    assert "architecture.md" in content
    assert "assets/feiyue-architecture.svg" in content
    assert "release-checklist.md" in content
    assert "cli-reference.md" in content
    assert "real-provider-integration-plan.md" in content
    assert "../CONTRIBUTING.md" in content
    assert "provider-free example smoke" in content
    assert "provider-free benchmark smoke" in content


def test_cli_reference_documents_phase_b_commands_and_safety_defaults() -> None:
    content = CLI_REFERENCE.read_text(encoding="utf-8")

    assert "# Feiyue CLI Reference" in content
    assert "feiyue-runs cli-reference" not in content  # generated command index, not recursive self-doc dependency
    assert "feiyue-runs semantic-review" in content
    assert "feiyue-runs creative-metrics-record" in content
    assert "feiyue-runs verify-production-promotion-readiness" in content
    assert "No command in this reference requires secrets to be written into docs." in content
    assert "Authorization: Bearer" not in content
    assert "PRIVATE KEY" not in content


def test_operator_docs_are_indexed_from_readme_and_docs_index() -> None:
    readme = README.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")

    for path in OPERATOR_DOCS:
        assert path.exists(), path
        rel = path.relative_to(REPO_ROOT).as_posix()
        assert rel in readme
        assert path.name in docs_index


def test_operator_docs_capture_safety_boundaries_and_required_phrases() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in OPERATOR_DOCS)

    assert "no global Hermes config mutation" in combined
    assert "dry_run_only: true" in combined
    assert "exact authorization" in combined
    assert "production PR/promotion disabled by default" in combined
    assert "rollback evidence" in combined
    assert "review inbox read-only" in combined
    assert "promotion_attempted: false" in combined


def test_operator_docs_include_actionable_local_cli_examples_without_live_execution() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in OPERATOR_DOCS)

    assert "python3 -m feiyue_core.workflow.runs_cli --root ../.. review-inbox --format json" in combined
    assert "approve-promotion <run_id>" in combined
    assert "promote-approved <run_id>" in combined
    assert "workflow-smoke <run_id>" in combined
    assert "workflow-promotion <run_id>" in combined
    assert "approve-routing-proposal" in combined
    assert "apply-approved-routing" in combined
    assert "approve-multi-worker-dry-run" in combined
    assert "run-approved-multi-worker-dry-run" in combined
    assert "PROVIDER_FREE_EXAMPLE_SMOKE_OK" in combined
    assert "BENCHMARK_SMOKE_OK" in combined
    assert "Do not execute live provider/profile calls unless" in combined


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
    assert "Current baseline: 640 passed" in content


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
        assert "Current verified baseline: `640 passed`" in content
        assert "Wave4-1F" in content
        assert "45/45 real Hermes profile calls" in content
        assert "gemini-3.1-pro" in content
        assert "M10 real profile benchmark lane usable" in content
        assert "M10 real multi-worker execution lane not yet implemented" in content


def test_status_docs_capture_wave4_2b_real_profile_workflow_smoke() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `640 passed`" in content
        assert "Wave4-2B" in content
        assert "WAVE4_2B_REAL_PROFILE_WORKFLOW_OK" in content
        assert "feiyue-weak-deepseek-flash" in content
        assert "provider_call_count: 1" in content
        assert "workflow_status: verified" in content


def test_status_docs_capture_wave4_2c_real_teacher_retry_smoke() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `640 passed`" in content
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
        assert "Current verified baseline: `640 passed`" in content
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
        assert "Current verified baseline: `640 passed`" in content
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
        assert "Current verified baseline: `640 passed`" in content
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
        assert "Current verified baseline: `640 passed`" in content
        assert "Wave4-5B" in content
        assert "MultiWorkerWorkflowDryRunOrchestrator" in content
        assert "feiyue-runs multi-worker-workflow" in content
        assert "wave4-5b-approved-multi-worker-dry-run-smoke" in content
        assert "multi_worker_plan_authorization_applies" in content
        assert "dry_run_only: true" in content
        assert "promotion_attempted: false" in content
        assert "global_hermes_config_mutated: false" in content


def test_status_docs_capture_wave4_5c_productized_multi_worker_dry_run_cli() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `640 passed`" in content
        assert "Wave4-5C" in content
        assert "approve-multi-worker-dry-run" in content
        assert "run-approved-multi-worker-dry-run" in content
        assert "wave4-5c-productized-dry-run-approval-smoke" in content
        assert "WAVE4_5C_PRODUCTIZED_DRY_RUN_APPROVAL_OK" in content
        assert "execute_multi_worker_workflow_dry_run" in content
        assert "dry_run_only: true" in content
        assert "promotion_attempted: false" in content


def test_status_docs_capture_remaining_a_f_foundations() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `640 passed`" in content
        assert "Wave4-5D" in content
        assert "--profile-runner fake|hermes" in content
        assert "MultiWorkerTeacherEscalationAuthorization" in content
        assert "read-only review inbox" in content
        assert "rollback simulation" in content

    assert "teacher_escalation_authorization_missing" in outline
    assert "CapabilityHistoryCollector" in outline
    assert "feiyue-runs capability-history --write-report" in outline
    assert "sandboxed curator asset promotion" in outline
    assert "feiyue-runs review-inbox --format json" in outline
    assert "PR-plan evidence" in outline


def test_status_docs_capture_parallel_batch1_foundations() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `640 passed`" in content
        assert "Batch1" in content
        assert "feiyue-runs live-smoke-plan --write-plan" in content
        assert "feiyue-runs longitudinal-gain --write-report" in content
        assert "/dashboard/review-inbox" in content
        assert "operator runbooks" in content or "operator-guide.md" in content
        assert "production PR/promotion" in content

    assert "LiveSmokePlanBuilder" in outline
    assert "production_side_effects_enabled: false" in outline
    assert "review-inbox/index.html" in outline
    assert "docs/security-boundaries.md" in outline


def test_status_docs_capture_curator_live_asset_loop() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `640 passed`" in content
        assert "feiyue-runs curator-live-proposal --write-proposal" in content
        assert "feiyue-runs promote-curator-asset" in content
        assert "live-b-real-teacher-retry-smoke-20260614" in content
        assert "asset-live-b-real-teacher-retry-20260614" in content
        assert "dry_run_only: true" in content
        assert "promotion_attempted: false" in content
        assert "global_hermes_config_mutated: false" in content

    assert ".hermes/lessons/asset-live-b-real-teacher-retry-20260614.md" in outline
    assert "Asset Reuse / Longitudinal Gain Smoke" in outline


def test_status_docs_capture_blueprint_status_sync_v2_frontier() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Blueprint Status Sync v2" in content
        assert "75–80%" in content or "75-80%" in content
        assert "Phase C live evidence ingestion" in content
        assert "real_creative_e2e" in content
        assert "longitudinal mini-program" in content
        assert "longitudinal-mini-program-20260614" in content
        assert "teacher_call_rate_delta -1.0" in content or "teacher_call_rate_delta `-1.0`" in content
        assert "real multi-worker project slice" in content

    assert "M10 Real Provider / Multi-Profile Worker Integration | Partial Real Workflow Lane" in outline
    assert "M11 Real Workflow Execution / Promotion | Partial Real Workflow + Gated Promotion" in outline
    assert "M9 Strategy/Evaluation Harness | Done Foundation++++" in outline
    assert "旧状态矩阵已压缩" in outline


def test_status_docs_capture_productized_teacher_retry_and_true_multi_student_plan() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")
    cli_reference = CLI_REFERENCE.read_text(encoding="utf-8")
    design = (REPO_ROOT / "docs" / "true-multi-student-planner-design.md").read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "run-approved-multi-worker-teacher-retry" in content
        assert "real-repo-4a-productized-teacher-retry-dry-run" in content
        assert "feiyue-mid-deepseek-pro" in content
        assert "feiyue-strong-gpt55" in content
        assert "true multi-student planner" in content
        assert "Current verified baseline: `640 passed`" in content

    assert "run-approved-multi-worker-teacher-retry" in cli_reference
    assert "one student + teacher retry" in design
    assert "multiple student workers" in design
    assert "merge strategy" in design
    assert "promotion remains out of scope" in design


def test_status_docs_capture_true_multi_student_5a_5d_and_6a_pr_plan_bridge() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")
    cli_reference = CLI_REFERENCE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "Current verified baseline: `640 passed`" in content
        assert "MultiStudentDryRunExecutor" in content
        assert "approve-true-multi-student-dry-run" in content
        assert "run-approved-true-multi-student-dry-run" in content
        assert "true-multi-student-workflow" in content
        assert "real-repo-5c-one-real-one-fake-dry-run" in content
        assert "real-repo-5d-all-real-multi-student-dry-run" in content
        assert "provider_call_count `2`" in content or "provider_call_count 2" in content
        assert "create_multi_student_pr_plan" in content
        assert "external_pr_created false" in content or "external_pr_created `false`" in content
        assert "mutates_production false" in content or "mutates_production `false`" in content

    assert "approve-true-multi-student-dry-run" in cli_reference
    assert "run-approved-true-multi-student-dry-run" in cli_reference
    assert "true-multi-student-workflow" in cli_reference


def test_status_docs_capture_6b_github_draft_pr_adapter_smoke() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")
    cli_reference = CLI_REFERENCE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "GitHubDraftPRAdapter" in content
        assert "create-approved-draft-pr --adapter github" in content
        assert "https://github.com/sinonchum/Feiyue/pull/2" in content
        assert "feiyue/6b-draft-pr-smoke" in content
        assert "isDraft true" in content or "isDraft `true`" in content
        assert "autoMergeRequest null" in content or "autoMergeRequest `null`" in content
        assert "no merge" in content or "no merge/deployment/production mutation" in content

    assert "create-approved-draft-pr <run_id> --adapter fake|github" in cli_reference


def test_status_docs_capture_7a_7d_real_feature_pr_readiness_chain() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "real-repo-7a-true-multi-student-feature-dry-run" in content
        assert "feiyue-mid-deepseek-pro" in content
        assert "feiyue-strong-gpt55" in content
        assert "https://github.com/sinonchum/Feiyue/pull/3" in content
        assert "feiyue/7b-real-feature-pr" in content
        assert "wave7-7c-pr3-semantic-safety-review" in content
        assert "wave7-7d-pr3-merge-readiness-evidence-only" in content
        assert "merge_performed `false`" in content or "merge_performed false" in content
        assert "auto_merge_enabled `false`" in content or "auto_merge_enabled false" in content
        assert "deploy_performed `false`" in content or "deploy_performed false" in content


def test_status_docs_capture_8a_merge_rollback_deploy_readiness_design() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")
    cli_reference = CLI_REFERENCE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "MergeRollbackDeployReadinessPlan" in content
        assert "wave8-8a-pr3-readiness-design" in content
        assert "approval_applies `true`" in content or "approval_applies true" in content
        assert "merge_performed `false`" in content or "merge_performed false" in content
        assert "auto_merge_enabled `false`" in content or "auto_merge_enabled false" in content
        assert "deploy_performed `false`" in content or "deploy_performed false" in content
        assert "production_mutated `false`" in content or "production_mutated false" in content

    assert "merge-rollback-deploy-readiness-plan" in cli_reference
    assert "approve-merge-rollback-deploy-readiness" in cli_reference
    assert "verify-merge-rollback-deploy-readiness" in cli_reference



def test_status_docs_capture_8b_approved_merge_execution_smoke() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")
    cli_reference = CLI_REFERENCE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "MergeExecutionApproval" in content
        assert "execute-approved-merge" in content
        assert "wave8-8b-pr3-fake-merge-smoke" in content
        assert "fake_adapter_simulated_merge_only" in content
        assert "pr_is_draft" in content
        assert "simulated_merge_performed `true`" in content or "simulated_merge_performed true" in content
        assert "merge_performed `false`" in content or "merge_performed false" in content
        assert "external_side_effect_performed `false`" in content or "external_side_effect_performed false" in content
        assert "deploy_performed `false`" in content or "deploy_performed false" in content
        assert "production_mutated `false`" in content or "production_mutated false" in content

    assert "approve-merge-execution" in cli_reference
    assert "execute-approved-merge" in cli_reference



def test_status_docs_capture_8c_pr_ready_for_review_transition_gate() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")
    cli_reference = CLI_REFERENCE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "PRReadyForReviewApproval" in content
        assert "approve-pr-ready-for-review" in content
        assert "transition-pr-ready-for-review" in content
        assert "wave8-8b-pr3-fake-merge-smoke" in content
        assert "fake_adapter_simulated_ready_for_review_only" in content
        assert "external_pr_mutation_not_authorized" in content
        assert "simulated_ready_for_review_performed `true`" in content or "simulated_ready_for_review_performed true" in content
        assert "ready_for_review_performed `false`" in content or "ready_for_review_performed false" in content
        assert "external_side_effect_performed `false`" in content or "external_side_effect_performed false" in content
        assert "merge_performed `false`" in content or "merge_performed false" in content
        assert "deploy_performed `false`" in content or "deploy_performed false" in content
        assert "production_mutated `false`" in content or "production_mutated false" in content

    assert "approve-pr-ready-for-review" in cli_reference
    assert "transition-pr-ready-for-review" in cli_reference



def test_status_docs_capture_8d_real_pr_ready_for_review_transition() -> None:
    readme = README.read_text(encoding="utf-8")
    outline = OUTLINE.read_text(encoding="utf-8")
    cli_reference = CLI_REFERENCE.read_text(encoding="utf-8")

    for content in (readme, outline):
        assert "PRReadyForReviewExternalMutationApproval" in content
        assert "approve-pr-ready-for-review-external-mutation" in content
        assert "--perform-external-mutation" in content
        assert "wave8-8d-pr3-real-ready-for-review-approval" in content
        assert "github_pr_marked_ready_for_review" in content
        assert "isDraft `false`" in content or "isDraft false" in content
        assert "ready_for_review_performed `true`" in content or "ready_for_review_performed true" in content
        assert "external_side_effect_performed `true`" in content or "external_side_effect_performed true" in content
        assert "merge_performed `false`" in content or "merge_performed false" in content
        assert "deploy_performed `false`" in content or "deploy_performed false" in content
        assert "production_mutated `false`" in content or "production_mutated false" in content

    assert "approve-pr-ready-for-review-external-mutation" in cli_reference
    assert "--perform-external-mutation" in cli_reference
