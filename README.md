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
```

Read-only API endpoints:

```text
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
- [`docs/resilient-session-runtime.md`](docs/resilient-session-runtime.md) — feature design for anti-amnesia runtime recovery across model fallback, network/power loss, and unknown side effects.
- [`docs/AI递归自我提升现状讨论 2026-06-12.md`](docs/AI递归自我提升现状讨论%202026-06-12.md) — discussion notes on practical Recursive Self-Improvement (RSI), synthetic data, self-play, AI feedback, inference-time self-correction, environment-driven feedback, and agent loops.

## Status

Private repository. Current baseline includes provider-free Feiyue core foundations through M9, the M10 safe provider/profile integration foundation, and the M11 provider-free toy workflow execution, fake teacher-guided retry, verified branch promotion, run report persistence with policy/action evidence sections plus machine-readable run-evidence indexes plus fallback handoff summaries, and M12 policy governor integration foundation with run-evidence loader, YAML policy config loader, exact-match human approval records, persisted approval.json artifacts, approval-aware fallback handoff summaries, `RunCatalog` aggregate summaries, read-only local API, and `feiyue-runs` local inspection CLI. Real provider smoke, Hermes profile execution, and real-project promotion remain gated on explicit authorization and configured credentials.
