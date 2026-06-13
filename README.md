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
# export writes index.html, manifest.json, and runs/<task_id>.html
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

Read-only API endpoints:

```text
GET /
GET /dashboard
GET /dashboard/runs/<task_id>
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
- [`docs/real-provider-integration-plan.md`](docs/real-provider-integration-plan.md) — plan-only sequence and safety checklist for explicitly authorized real provider execution, Hermes profile subprocess smoke, teacher escalation, and real weak/strong benchmark work.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution rules for TDD, provider-free defaults, secret handling, and CI expectations.
- [`docs/resilient-session-runtime.md`](docs/resilient-session-runtime.md) — feature design for anti-amnesia runtime recovery across model fallback, network/power loss, and unknown side effects.
- [`docs/AI递归自我提升现状讨论 2026-06-12.md`](docs/AI递归自我提升现状讨论%202026-06-12.md) — discussion notes on practical Recursive Self-Improvement (RSI), synthetic data, self-play, AI feedback, inference-time self-correction, environment-driven feedback, and agent loops.

## Status

Private repository. Current baseline includes provider-free Feiyue core foundations through M9; M6 asset proposal persistence/review/promotion-gate writer; M9 benchmark case and trace-fixture preparation contracts; M10 safe provider/profile integration foundation plus real-provider plan-only authorization checklist, typed authorization/evidence records, and gated Hermes profile subprocess runner; M11 provider-free workflow execution, bounded multi-round fake teacher retry, verified branch promotion, production-promotion safety/rollback boundary, and run report persistence; M12 policy governor, budget/risk/privacy gates, exact-match human approval, action evidence, run-evidence indexes, and fallback handoff summaries; M13 `feiyue-runs` CLI, `RunCatalog`, read-only local API/dashboard/drill-down, read-only asset catalog, static HTML export, manifest hashing/verifier, portable bundle, and export-all pipeline; M9/M10 live-benchmark and multi-worker routing contracts that fail closed without explicit authorization; and M14 GitHub Actions CI gates with compileall, pytest, static export-all smoke, provider-free example smoke, provider-free benchmark smoke, release checklist, contributing guide, architecture doc, static docs index, SVG architecture diagram, secret scan, CI contract tests, and Node24 actions runtime opt-in. Current verified baseline: `517 passed`. Wave4-1F established the real Hermes profile benchmark checkpoint: 45/45 real Hermes profile calls passed across weak/mid/strong profiles, with `gemini-3.1-pro` now the canonical Gemini strong model. M10 real profile benchmark lane usable; M10 real multi-worker execution lane not yet implemented. Wave4-2B real profile workflow smoke passed with marker `WAVE4_2B_REAL_PROFILE_WORKFLOW_OK`: `feiyue-weak-deepseek-flash` produced a sandboxed toy-repo patch with provider_call_count: 1, workflow_status: verified, verifier pass, promotion-ready report, and clean source checkout. Wave4-2C real teacher retry smoke passed with marker `WAVE4_2C_REAL_TEACHER_RETRY_OK`: `feiyue-weak-deepseek-flash` produced a controlled failing first patch, `feiyue-strong-gpt55` provided teacher guidance, provider_call_count: 3, initial_workflow_status: needs_teacher, final_workflow_status: verified, retry_performed true, and clean source checkout. Wave4-2D productized that bridge into `RealProfileWorkflowRunner` plus `feiyue-runs workflow-smoke` evidence inspection, with fake-first contracts for worker/teacher retry evidence and redacted `.hermes/workflow-smokes/<run_id>/` reports. Wave4-3A added real-project-style dry-run semantics: dry_run_only: true, promotion_attempted: false, verifier-backed promotion_ready may be true, but no production promotion is attempted. Wave4-3B-1 added `RealProfilePromotionApproval` for exact approval binding to run_id/task_id/changed_files/target_branch/source_commit_sha/workflow_report_hash; Wave4-3B-2 added `RealProfilePromotionGate` plus `feiyue-runs workflow-promotion` evidence inspection, with fail-closed `missing_promotion_approval` and success-path `promotion_approval_applies` contracts. Wave4-3B-3 executed a low-risk real-project branch-only promotion smoke with run_id `wave4-3b-3-low-risk-real-project-promotion-smoke-v3`, target branch `feiyue/w43b-approved-promotion-smoke`, promoted commit `66f6055fec5a90f192b78bc6719e6938d46ba053`, remote branch verification, and clean main checkout. Wave4-3C productized approval into `feiyue-runs approve-promotion` and `feiyue-runs promote-approved`, then executed run_id `wave4-3c-productized-approval-cli-smoke-v2` into target branch `feiyue/w43c-productized-approval-cli-smoke` with promoted commit `d8370868a992320590d23865b2e77099b57930ad` and remote branch verification. Wave4-4 added `CapabilityFeedbackAggregator` and `feiyue-runs capability-feedback --write-report` to summarize workflow-smoke/workflow-promotion evidence into audit-only `latest.json` and `latest.md` reports with `routing_table_mutated: false`; routing table changes remain recommendations only. Wave4-4B added `RoutingProposalGenerator` and `feiyue-runs routing-proposal --proposal-id wave4-4b-routing-proposal-smoke --write-proposal` to produce human-reviewed routing proposals with `requires_human_approval: true`, source feedback/routing hashes, and `routing_table_mutated: false`. Wave4-4C added `RoutingApplyGate`, `approve-routing-proposal`, and `apply-approved-routing` for exact approval-gated routing updates; smoke `wave4-4c-routing-apply-smoke` applied only after `routing_proposal_approval_applies`, mutated a temporary routing table to `steady-4c`, and cleaned local artifacts. Wave4-5 added `MultiWorkerOrchestrationPlanner` and `feiyue-runs multi-worker-plan` to create provider-free multi-worker route plans from approved routing/apply evidence; smoke `wave4-5-multi-worker-orchestration-smoke` selected `steady-4c` with `routing_apply_evidence_loaded`, `provider_execution_requested: false`, and `global_hermes_config_mutated: false`. Real-project promotion remains gated on exact explicit authorization and configured credentials.
