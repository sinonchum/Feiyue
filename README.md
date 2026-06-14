# Feiyue

Feiyue is a private research/design repository for a Hermes-based Creative Evolution Loop Orchestrator: a self-evolving AI development organization that turns human creative direction into strong-model PRD/spec/task contracts, weak-model execution, tool-grounded verification, teacher-guided repair, and reusable skills/evals/templates/routing rules. Its canonical direction is to make weaker/cheaper student models increasingly reliable, expand their task boundary with evidence, and gradually develop system roles that can contribute creative variants and opportunities under human taste selection.

## Implementation

- Core package: `packages/feiyue-core`
- Current slice: Pydantic schema contracts, recovery-runtime data contracts, command execution, JSONL trace writing, pytest verification, isolated worktree execution, session journal, recovery manifest persistence, recovery prompt generation, operation recording, local-loop recovery integration, reconciliation, resume context preparation, side-effect inspection, inspector-backed reconciliation, persisted resume cleanup, automatic file/git/artifact side-effect check recording, full interruption resume simulation, high-risk recovery safety gating, git remote/GitHub ref reconciliation, CLI demo entrypoint, LocalLoop crash simulation, deterministic candidate generation, verification feedback analysis, candidate revision loop, role-aware fake student/teacher provider contracts, teacher intervention policy, model role router, structured candidate output parsing, prompt template versioning, candidate service orchestration, toy student/teacher iteration loop, persisted iteration trace, trace replay resume context, iteration fallback resume prompt, and provider-free iteration resume demo, project knowledge layer, task contract rendering, bug dossier models, lesson packet models, regression eval assets, model routing table assets, curator input bundles, distillation proposal models, teacher guidance normalizer, curation review gate, capability ladder, worker performance records, model capability profiles, capability recommendation rules, creative briefs, creative variant schemas, creative critiques, user selection feedback, strategy evaluation records, strategy scorecards, benchmark task suites, strategy comparison reports, fake Hermes profile runner integration, provider failure diagnostics/redaction, provider profile integration smoke, provider-free toy workflow execution, sandboxed candidate file writes, verifier-gated promotion readiness, bug dossier generation on failure, fake teacher-guided retry, verified patch promotion to target branches, persisted workflow/teacher/promotion reports, M12 policy/action evidence, run-evidence indexes, approval-aware fallback handoff summaries, `RunCatalog` aggregate summaries, read-only local API, and `feiyue-runs` CLI for listing/showing/handoff rendering.
- Local test command:

```bash
cd packages/feiyue-core
python3 -m pytest tests/ -q
```

- Interruption/resume demo command:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.runtime.interruption_simulation --root /tmp/feiyue-demo --json
```

- Run evidence CLI commands:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. list
python3 -m feiyue_core.workflow.runs_cli --root ../.. list --json
python3 -m feiyue_core.workflow.runs_cli --root ../.. show <task_id>
python3 -m feiyue_core.workflow.runs_cli --root ../.. handoff <task_id>
python3 -m feiyue_core.workflow.runs_api --root ../.. --host 127.0.0.1 --port 8765
python3 -m feiyue_core.workflow.runs_export --root ../.. --out ../../.hermes/static-runs-report
python3 -m feiyue_core.workflow.runs_export_verify ../../.hermes/static-runs-report/manifest.json
python3 -m feiyue_core.workflow.runs_export_bundle --report ../../.hermes/static-runs-report --out ../../.hermes/static-runs-report.zip
python3 -m feiyue_core.workflow.runs_export_all --root ../.. --out ../../.hermes/static-runs-report --bundle ../../.hermes/static-runs-report.zip
# export writes index.html, manifest.json, assets/index.html, review-inbox/index.html, and runs/<task_id>.html
```

- Provider-free example smoke command:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.examples.provider_free_smoke \
  --root /tmp/feiyue-provider-free-example \
  --out /tmp/feiyue-provider-free-example-report \
  --bundle /tmp/feiyue-provider-free-example-report.zip
# expected marker: PROVIDER_FREE_EXAMPLE_SMOKE_OK
```

- Provider-free benchmark smoke command:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.evaluation.benchmark_runner \
  --quick \
  --output /tmp/feiyue-benchmark.json \
  --output-markdown /tmp/feiyue-benchmark.md
# expected marker: BENCHMARK_SMOKE_OK
```

- Creative-to-execution provider-free E2E smoke command:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.creative.e2e_smoke \
  --root ../.. \
  --run-id wave5-5-local \
  --seed "Turn a human creative seed into a verifier-backed task contract" \
  --write-report
# console script when installed: creative-e2e-smoke --run-id wave5-5-local --seed "..." --write-report
# writes ../../.hermes/creative-e2e/wave5-5-local/evidence.json and report.md
# expected marker: CREATIVE_E2E_SMOKE_OK
```

Read-only API endpoints:

```text
GET /
GET /dashboard
GET /dashboard/assets
GET /dashboard/review-inbox
GET /dashboard/runs/<task_id>
GET /assets
GET /review-inbox
GET /runs
GET /runs/<task_id>
GET /runs/<task_id>/handoff
```

## Documents

- [`docs/Feiyue-master-blueprint.md`](docs/Feiyue-master-blueprint.md) — highest-level canonical blueprint for Feiyue as a Hermes-based Creative Evolution Loop Orchestrator: human creativity, strong-model specification, weak-model execution, tool-grounded verification, teacher-guided repair, asset distillation, weak-model capability expansion, and emerging creative roles.
- [`docs/Feiyue-system-doctrine.md`](docs/Feiyue-system-doctrine.md) — canonical doctrine for Feiyue's system-level self-evolution, student/teacher model roles, sparse teacher intervention, distillation, and cross-model quality preservation. Future plans and development default to this doctrine unless explicitly overridden.
- [`docs/Feiyue-self-evolution-development-outline.md`](docs/Feiyue-self-evolution-development-outline.md) — canonical v2 development plan derived from the Master Blueprint, covering completed code assets, upcoming milestones, feature scope, tech stack, dependencies, parallel/serial work, and two-track functional/cleanliness acceptance gates.
- [`docs/Feiyue-PRD.md`](docs/Feiyue-PRD.md) — product requirements for a verifiable feedback-driven AI self-improvement system.
- [`docs/Feiyue-development-outline.md`](docs/Feiyue-development-outline.md) — detailed development outline, dependencies, parallelization plan, serial blockers, risks, and solution paths.
- [`docs/index.md`](docs/index.md) — static docs index for canonical direction, architecture, release gates, contribution rules, and provider-free smoke surfaces.
- [`docs/architecture.md`](docs/architecture.md) — provider-free architecture flow, roles, evidence/handoff surfaces, and gated future work.
- [`docs/assets/feiyue-architecture.svg`](docs/assets/feiyue-architecture.svg) — static flat SVG diagram of the Feiyue provider-free workflow.
- [`docs/release-checklist.md`](docs/release-checklist.md) — release gate checklist covering local commands, CI requirements, secret scan, and authorization boundaries.
- [`docs/cli-reference.md`](docs/cli-reference.md) — stable `feiyue-runs` command reference covering evidence inspection, approval-gated operations, semantic review, and creative metrics commands.
- [`docs/operator-guide.md`](docs/operator-guide.md) — operator entrypoint for daily checks, evidence paths, no global Hermes config mutation, and dry-run defaults.
- [`docs/approval-runbooks.md`](docs/approval-runbooks.md) — exact authorization procedures for promotion, routing, and multi-worker dry-run approvals.
- [`docs/live-smoke-playbook.md`](docs/live-smoke-playbook.md) — provider-free rehearsal, live/profile smoke authorization checklist, and abort gates.
- [`docs/security-boundaries.md`](docs/security-boundaries.md) — forbidden actions, review inbox read-only behavior, secrets, and production PR/promotion disabled by default.
- [`docs/rollback-guide.md`](docs/rollback-guide.md) — rollback evidence requirements, local rollback simulation, and stop conditions.
- [`docs/real-provider-integration-plan.md`](docs/real-provider-integration-plan.md) — plan-only sequence and safety checklist for explicitly authorized real provider execution, Hermes profile subprocess smoke, teacher escalation, and real weak/strong benchmark work.
- [`docs/real-multi-worker-live-dry-run.md`](docs/real-multi-worker-live-dry-run.md) — Wave5-3 fake-first/fail-closed CLI seam for authorized real Hermes multi-worker dry-run evidence under `.hermes/real-multi-worker-runs/<run_id>/evidence.json`.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution rules for TDD, provider-free defaults, secret handling, and CI expectations.
- [`docs/resilient-session-runtime.md`](docs/resilient-session-runtime.md) — feature design for anti-amnesia runtime recovery across model fallback, network/power loss, and unknown side effects.
- [`docs/AI递归自我提升现状讨论 2026-06-12.md`](docs/AI递归自我提升现状讨论%202026-06-12.md) — discussion notes on practical Recursive Self-Improvement (RSI), synthetic data, self-play, AI feedback, inference-time self-correction, environment-driven feedback, and agent loops.

## Status

Private repository. Current baseline includes provider-free Feiyue core foundations through M9; M6 asset proposal persistence/review/promotion-gate writer; M9 benchmark case and trace-fixture preparation contracts; M10 safe provider/profile integration foundation plus real-provider plan-only authorization checklist, typed authorization/evidence records, and gated Hermes profile subprocess runner; M11 provider-free workflow execution, bounded multi-round fake teacher retry, verified branch promotion, production-promotion safety/rollback boundary, and run report persistence; M12 policy governor, budget/risk/privacy gates, exact-match human approval, action evidence, run-evidence indexes, and fallback handoff summaries; M13 `feiyue-runs` CLI, `RunCatalog`, read-only local API/dashboard/drill-down, read-only asset catalog, static HTML export, manifest hashing/verifier, portable bundle, and export-all pipeline; M9/M10 live-benchmark and multi-worker routing contracts that fail closed without explicit authorization; and M14 GitHub Actions CI gates with compileall, pytest, static export-all smoke, provider-free example smoke, provider-free benchmark smoke, release checklist, contributing guide, architecture doc, static docs index, SVG architecture diagram, secret scan, CI contract tests, and Node24 actions runtime opt-in. Current verified baseline: `631 passed`. Wave4-1F established the real Hermes profile benchmark checkpoint: 45/45 real Hermes profile calls passed across weak/mid/strong profiles, with `gemini-3.1-pro` now the canonical Gemini strong model. M10 real profile benchmark lane usable; M10 real multi-worker execution lane not yet implemented. Wave4-2B real profile workflow smoke passed with marker `WAVE4_2B_REAL_PROFILE_WORKFLOW_OK`: `feiyue-weak-deepseek-flash` produced a sandboxed toy-repo patch with provider_call_count: 1, workflow_status: verified, verifier pass, promotion-ready report, and clean source checkout. Wave4-2C real teacher retry smoke passed with marker `WAVE4_2C_REAL_TEACHER_RETRY_OK`: `feiyue-weak-deepseek-flash` produced a controlled failing first patch, `feiyue-strong-gpt55` provided teacher guidance, provider_call_count: 3, initial_workflow_status: needs_teacher, final_workflow_status: verified, retry_performed true, and clean source checkout. Wave4-2D productized that bridge into `RealProfileWorkflowRunner` plus `feiyue-runs workflow-smoke` evidence inspection, with fake-first contracts for worker/teacher retry evidence and redacted `.hermes/workflow-smokes/<run_id>/` reports. Wave4-3A added real-project-style dry-run semantics: dry_run_only: true, promotion_attempted: false, verifier-backed promotion_ready may be true, but no production promotion is attempted. Wave4-3B-1 added `RealProfilePromotionApproval` for exact approval binding to run_id/task_id/changed_files/target_branch/source_commit_sha/workflow_report_hash; Wave4-3B-2 added `RealProfilePromotionGate` plus `feiyue-runs workflow-promotion` evidence inspection, with fail-closed `missing_promotion_approval` and success-path `promotion_approval_applies` contracts. Wave4-3B-3 executed a low-risk real-project branch-only promotion smoke with run_id `wave4-3b-3-low-risk-real-project-promotion-smoke-v3`, target branch `feiyue/w43b-approved-promotion-smoke`, promoted commit `66f6055fec5a90f192b78bc6719e6938d46ba053`, remote branch verification, and clean main checkout. Wave4-3C productized approval into `feiyue-runs approve-promotion` and `feiyue-runs promote-approved`, then executed run_id `wave4-3c-productized-approval-cli-smoke-v2` into target branch `feiyue/w43c-productized-approval-cli-smoke` with promoted commit `d8370868a992320590d23865b2e77099b57930ad` and remote branch verification. Wave4-4 added `CapabilityFeedbackAggregator` and `feiyue-runs capability-feedback --write-report` to summarize workflow-smoke/workflow-promotion evidence into audit-only `latest.json` and `latest.md` reports with `routing_table_mutated: false`; routing table changes remain recommendations only. Wave4-4B added `RoutingProposalGenerator` and `feiyue-runs routing-proposal --proposal-id wave4-4b-routing-proposal-smoke --write-proposal` to produce human-reviewed routing proposals with `requires_human_approval: true`, source feedback/routing hashes, and `routing_table_mutated: false`. Wave4-4C added `RoutingApplyGate`, `approve-routing-proposal`, and `apply-approved-routing` for exact approval-gated routing updates; smoke `wave4-4c-routing-apply-smoke` applied only after `routing_proposal_approval_applies`, mutated a temporary routing table to `steady-4c`, and cleaned local artifacts. Wave4-5 added `MultiWorkerOrchestrationPlanner` and `feiyue-runs multi-worker-plan` to create provider-free multi-worker route plans from approved routing/apply evidence; smoke `wave4-5-multi-worker-orchestration-smoke` selected `steady-4c` with `routing_apply_evidence_loaded`, `provider_execution_requested: false`, and `global_hermes_config_mutated: false`. Wave4-5B added `MultiWorkerWorkflowDryRunOrchestrator` and `feiyue-runs multi-worker-workflow` evidence inspection to execute approved multi-worker plans as dry-run-only workflows; smoke `wave4-5b-approved-multi-worker-dry-run-smoke` selected `steady-4c`, recorded `multi_worker_plan_authorization_applies`, kept dry_run_only: true, promotion_attempted: false, and global_hermes_config_mutated: false. Wave4-5C productized that authorization into `approve-multi-worker-dry-run` and `run-approved-multi-worker-dry-run`; smoke `wave4-5c-productized-dry-run-approval-smoke` created persisted approval for `execute_multi_worker_workflow_dry_run`, ran the approved fake-worker dry-run, emitted `WAVE4_5C_PRODUCTIZED_DRY_RUN_APPROVAL_OK`, and preserved dry_run_only: true plus promotion_attempted: false. Wave4-5D/A added the authorization-gated Hermes profile runner seam (`--profile-runner fake|hermes`) for selected-worker multi-worker dry-runs; Wave4-5E/B added fail-closed multi-worker teacher escalation authorization (`MultiWorkerTeacherEscalationAuthorization`) and fake retry evidence; Wave4-6/C added longitudinal capability history reports; Wave4-6D added sandboxed curator asset promotion with dedup/rollback evidence; Wave4-6E added a read-only review inbox; Wave4-6F added local-only promotion PR-plan and rollback simulation contracts. Batch1 added `feiyue-runs live-smoke-plan --write-plan` for exact-authorized live A/B smoke readiness without live calls, `feiyue-runs longitudinal-gain --write-report` for before/after capability trend reports, read-only `/review-inbox` and `/dashboard/review-inbox` surfaces plus static export coverage, and operator runbooks for approvals, live smoke, security boundaries, and rollback. Real-project production promotion remains gated on exact explicit authorization, review, rollback, and configured credentials.


## Latest verified live asset loop

The first curator live asset loop has completed on verified Live B evidence. `feiyue-runs curator-live-proposal --write-proposal` converted `live-b-real-teacher-retry-smoke-20260614` into review-required proposal `asset-live-b-real-teacher-retry-20260614`; `feiyue-runs promote-curator-asset --proposal-id ... --patch-id lesson --rollback-ref ...` then approved and promoted the project-local lesson `.hermes/lessons/asset-live-b-real-teacher-retry-20260614.md` with rollback evidence. Distillation bundles can now promote their lesson, regression_eval, and task_template patches separately by `--patch-id` (or `--patch-index`), with per-patch promotion evidence under `.hermes/asset-proposals/<proposal_id>/promotions/`. The loop requires verified dry-run evidence, first verifier failure, teacher-guided retry, final verifier pass, `dry_run_only: true`, `promotion_attempted: false`, and `global_hermes_config_mutated: false`; production PR/promotion remains disabled by default.

## Wave5-1 asset reuse / longitudinal gain smoke

Status: provider-free dry-run harness implemented. `feiyue-runs asset-reuse-smoke --run-id <id> --lesson-path .hermes/lessons/<lesson>.md --write-report` loads a promoted project-local lesson from `.hermes/lessons`, injects it into a comparable deterministic smoke, and writes `.hermes/asset-reuse/<run_id>/evidence.json` plus `report.md`. Evidence is shaped for longitudinal/capability history follow-up and records `dry_run_only: true`, `promotion_attempted: false`, and `global_hermes_config_mutated: false`. Expected baseline remains a placeholder until a reviewed project-local lesson and longitudinal sample set are run together; do not infer production lift from the dry-run smoke alone.

## Wave5-5 creative-to-execution E2E smoke

Status: provider-free dry-run implemented. `creative-e2e-smoke --run-id <id> --seed <human-seed> --write-report` (or `python3 -m feiyue_core.creative.e2e_smoke`) creates a deterministic `CreativeBrief`, variants, critiques, selected-variant feedback, PRD/spec text, a `TaskContract`, and a fake verified workflow report. It persists curator-ready evidence under `.hermes/creative-e2e/<run_id>/evidence.json` and optional `report.md`. Evidence records `dry_run_only: true`, `promotion_attempted: false`, `curator_proposal_ready: true`, and `global_hermes_config_mutated: false`; no provider/profile calls, global Hermes mutation, or production promotion are attempted by default.

## Blueprint Status Sync v2

Feiyue is now approximately **75–80%** complete against the Master Blueprint as an engineering system: provider-free safety foundations, real Hermes profile evidence, Phase C live evidence ingestion, `real_creative_e2e` creative dry-run evidence, capability-history, longitudinal-gain reporting, and approval-gated promotion/release seams are implemented and CI-verified. The remaining frontier is no longer broader profile repetition; the first targeted **longitudinal mini-program** has run as `longitudinal-mini-program-20260614`, proving a provider-free 3-batch measurement path with teacher_call_rate_delta -1.0, retry_count_delta -2, and repeat_error_count_delta -2. 4A productized sequenced real teacher retry with `run-approved-multi-worker-teacher-retry`; real Feiyue repo smoke `real-repo-4a-productized-teacher-retry-dry-run` verified `feiyue-mid-deepseek-pro` + `feiyue-strong-gpt55` with provider_call_count 3, retry_performed true, dry_run_only true, and no promotion/global mutation. 4C captured the next **true multi-student planner** design in `docs/true-multi-student-planner-design.md`; 5A/5B implemented `MultiStudentDryRunExecutor` plus `approve-true-multi-student-dry-run`, `run-approved-true-multi-student-dry-run`, and `true-multi-student-workflow` evidence inspection with `reject_on_conflict` merge handling. 5C real Feiyue repo smoke `real-repo-5c-one-real-one-fake-dry-run` verified one real profile plus one fake profile with source worktree clean; 5D smoke `real-repo-5d-all-real-multi-student-dry-run` verified `feiyue-mid-deepseek-pro` + `feiyue-strong-gpt55` as distinct student assignments, provider_call_count 2, conflict_files empty, dry_run_only true, promotion_attempted false, and global_hermes_config_mutated false. 6A added `create_multi_student_pr_plan`, then planned and exact-approved a local-only fake draft PR from the 5D evidence with approval_applies true, external_pr_created false, auto_merge false, and mutates_production false. 6B added `GitHubDraftPRAdapter` plus `create-approved-draft-pr --adapter github`, then created real GitHub draft PR #2 (`https://github.com/sinonchum/Feiyue/pull/2`) from `feiyue/6b-draft-pr-smoke` to `main`; verification showed isDraft true, state OPEN, autoMergeRequest null, checks passed, and no merge/deployment/production mutation. 7A ran `real-repo-7a-true-multi-student-feature-dry-run` with two real profiles (`feiyue-mid-deepseek-pro` and `feiyue-strong-gpt55`), provider_call_count 2, conflict_files empty, combined verifier passed, dry_run_only true, and no promotion/global mutation. 7B promoted the verified sandbox diff into real feature Draft PR #3 (`https://github.com/sinonchum/Feiyue/pull/3`) on branch `feiyue/7b-real-feature-pr`; 7C attached provider-free semantic/safety review evidence `wave7-7c-pr3-semantic-safety-review` to the PR body via REST PATCH after `gh pr edit` scope checks failed; 7D generated merge-readiness evidence only (`wave7-7d-pr3-merge-readiness-evidence-only`) with PR checks passed, isDraft true, autoMergeRequest null, merge_performed false, auto_merge_enabled false, deploy_performed false, and production_mutated false. The next frontier is the real multi-worker project slice beyond evidence-only readiness: explicitly approved merge/rollback/deploy operations after human review. 8A added `MergeRollbackDeployReadinessPlan`, exact `approve-merge-rollback-deploy-readiness`, and `verify-merge-rollback-deploy-readiness`; smoke `wave8-8a-pr3-readiness-design` bound PR #3's 7D merge-readiness evidence, rollback plan, deploy plan, and post-merge verification plan, then verified status `ready` with approval_applies true while keeping merge_performed false, auto_merge_enabled false, deploy_performed false, and production_mutated false. 8B added `MergeExecutionApproval`, exact `approve-merge-execution`, and `execute-approved-merge`; smoke `wave8-8b-pr3-fake-merge-smoke` approved a fake adapter execution over the 8A readiness report, recorded `fake_adapter_simulated_merge_only` with simulated_merge_performed `true`, merge_performed `false`, external_side_effect_performed `false`, deploy_performed `false`, and production_mutated `false`, while the GitHub adapter inspection blocked PR #3 with `pr_is_draft` before any merge side effect.

## Wave5 completion status

Wave5-1 through Wave5-6 have been implemented as fake-first / dry-run-safe productized seams. Wave5-1 loads promoted lessons and emits asset-reuse longitudinal evidence; Wave5-2 promotes lesson/regression_eval/task_template bundle patches separately with per-patch rollback evidence; Wave5-3 persists authorized real multi-worker dry-run history evidence while tests and smoke use fake runners; Wave5-4 creates draft PR plans/approvals/fake draft PR evidence with `auto_merge: false`; Wave5-5 runs provider-free creative seed → variant → PRD/spec → task contract → verified workflow evidence; Wave5-6 verifies release-candidate readiness with CI, rollback, exact production approval, and `production_mutated: false` dry-run evidence. Phase B productization adds disabled write-side review UI controls, generated `docs/cli-reference.md`, provider-free semantic review evidence, and creative proposal acceptance/taste metrics. Real external PR creation, merge, deployment, and production mutation remain disabled unless separately authorized with credentials and rollback approval.

