# Feiyue

> A self-evolving AI development orchestrator — strong models specify, weak models execute, deterministic verifiers gate quality, and the system learns from every run.

Feiyue is an open-source framework for building **verification-gated, evidence-driven AI agent workflows**. It addresses a practical problem in LLM-based development: strong models (GPT-5, Claude 4) are reliable but expensive, while weaker models (DeepSeek, Llama) are cheap but unreliable for complex tasks. Feiyue separates the roles — strong models for specification and oversight, weak models for bounded execution — with deterministic verification as the ground truth for pass/fail. Every operation produces auditable evidence, and successful patterns are distilled into reusable assets that compound over time.

## Why Feiyue

Teams building LLM-based agent systems commonly hit three problems:

- **Cost vs. quality**: Using capable models for everything is prohibitively expensive. Using cheap models alone produces unreliable results.
- **No ground truth**: Models report success, but there is no independent verification. Failures compound silently.
- **No learning**: Each run starts from scratch. Successful strategies and failure modes are not captured as reusable knowledge.

Feiyue addresses these with a structured orchestration loop:

```
Human Direction → Strong Model (Spec) → Task Contract → Weak Model (Execute)
  → Verifier → Policy Governor → Evidence → Curator → Assets
```

## Architecture

### The Evolution Loop

| Component | Role |
|---|---|
| **Strong Model** | Specification, task decomposition, sparse teacher guidance |
| **Weak Model** | Bounded execution using cost-efficient inference |
| **Verifier** | Deterministic pass/fail — the single source of truth |
| **Policy Governor** | Budget, risk, privacy, and human-approval gates |
| **Curator** | Distills successful patterns into lessons and evaluation cases |

### Key Concepts

**Strong/Weak Separation** — Strong models define what to build and how to verify success. Weak models execute within sandboxed boundaries. This lets teams reserve capable models for direction and oversight while using cost-effective models for the bulk of execution.

**Verifier-Gated Execution** — A workflow is not considered successful because a model says so. It is successful only when the verifier and persisted evidence agree. Failures trigger teacher-guided retry within bounded budgets.

**Evidence-First Design** — Every operation — execution, retry, promotion, approval — produces typed, persisted evidence. This replaces model self-reporting with auditable records suitable for compliance, rollback, and longitudinal analysis.

**Policy-Governed Safety** — High-risk operations (retries, teacher calls, promotions, production changes) pass through typed policy gates before any side effect. Gates produce auditable decisions and escalate to human approval when required.

**Asset Distillation** — Successful runs produce lessons, regression evaluation cases, and task templates. These are promoted through a curator review gate and reused in future runs, compounding capability gains and reducing teacher dependence over time.

## Feiyue + Hermes

Feiyue is built on top of [Hermes Agent](https://hermes-agent.nousresearch.com) — an open-source AI agent framework by Nous Research. The relationship is a layered one:

```
Feiyue (orchestration, verification, curation, evidence)
  └─ Hermes Agent (profiles, tool calling, model routing, sessions)
       └─ LLM Providers (OpenAI, Anthropic, DeepSeek, local, etc.)
```

### How they nest

**Hermes profiles as the execution layer** — Feiyue defines named Hermes profiles for each model role (`feiyue-weak-deepseek-flash`, `feiyue-mid-deepseek-pro`, `feiyue-strong-gpt55`, etc.). When Feiyue needs to dispatch a task, it launches a Hermes profile subprocess with the appropriate model and toolset. The profile handles the actual model call, while Feiyue handles verification, policy gates, and evidence persistence.

**Hermes Bridge** — The Feiyue operator console uses a Hermes Bridge sidecar to launch or resume Hermes sessions under explicit controls. The browser is an operator surface, not an agent runtime. Approved intents flow through Feiyue's policy gates before reaching a Hermes profile. Results write back as evidence under `.hermes/`.

**Skill integration** — Feiyue's promoted lessons and routing rules can be consumed by Hermes as skills. When Hermes runs in a project that uses Feiyue, it loads these assets to benefit from accumulated learning — fewer teacher calls, fewer retries, and better model routing.

**Closed loop** — Hermes executes the work; Feiyue verifies the result, records the evidence, and distills reusable knowledge. On the next run, that knowledge feeds back through Hermes profiles as improved lessons, routing, and task templates.

## Multi-Machine Sync

Feiyue is designed to share its accumulated learning across multiple Hermes instances — for example, a Windows workstation and a MacBook, or a team of developers.

### Sync layer

The Feiyue GitHub repository is the canonical sync medium. It holds the shared learning kernel:

| Syncs via Feiyue repo | Stays local |
|---|---|
| Promoted lessons (`.hermes/lessons/`) | API keys and OAuth tokens |
| Regression evaluation cases (`.hermes/evals/`) | Gateway session databases |
| Task templates (`.hermes/task-templates/`) | Machine-specific cron state |
| Routing rules (`.hermes/model-routing.yaml`) | Raw chat history and dumps |
| Hermes Bridge scripts and CI patterns | Local memory and user profile |

### Workflow

Before starting a major task on any machine:

```bash
# Pull the latest shared learning
cd ~/work/Feiyue
git pull --ff-only

# Install any new skills or bridge scripts
python tools/hermes-bridge/install_local_assets.py --install-skill --install-bridge
```

Then work inside the target project. After finishing:

```bash
# Commit new lessons, evals, or routing improvements
cd ~/work/Feiyue
git add .hermes/lessons/ .hermes/evals/ .hermes/task-templates/
git commit -m "feat: lessons from ..."
git push
```

The other machine pulls before its next session and benefits from the accumulated learning without sharing secrets or fragile local state.

## Project Structure

```
Feiyue/
├── packages/feiyue-core/      # Core engine (Python)
│   ├── feiyue_core/
│   │   ├── audit/              # Evidence and audit trails
│   │   ├── candidates/         # Candidate output management
│   │   ├── capability/         # Capability profiling and routing
│   │   ├── creative/           # Creative briefs and variant generation
│   │   ├── curation/           # Asset promotion and review gates
│   │   ├── evaluation/         # Benchmarks and evaluation runner
│   │   ├── generation/         # Prompt templates and generation
│   │   ├── orchestrator/       # Workflow orchestration
│   │   ├── providers/          # Model provider interfaces
│   │   ├── recovery/           # Session resilience and recovery
│   │   ├── routing/            # Model routing tables
│   │   ├── runtime/            # Runtime contracts and simulation
│   │   ├── safety/             # Policy governor and safety gates
│   │   ├── sandbox/            # Sandboxed execution environment
│   │   ├── schemas/            # Pydantic schema contracts
│   │   ├── verifiers/          # Deterministic verification
│   │   └── workflow/           # CLI, API, export, execution
│   ├── tests/                  # 725+ deterministic tests
│   └── pyproject.toml
├── docs/                       # Public documentation
├── examples/                   # Provider-free examples
├── scripts/                    # Utility scripts
└── tools/                      # Development tools
```

## Getting Started

### Prerequisites

- Python 3.11+
- No API keys required for provider-free mode

### Install

```bash
cd packages/feiyue-core
pip install -e '.[dev]'
```

### Run the provider-free smoke test

```bash
python -m feiyue_core.examples.provider_free_smoke \
  --root /tmp/feiyue-example \
  --out /tmp/feiyue-example-report \
  --bundle /tmp/feiyue-example-report.zip
```

Expected marker: `PROVIDER_FREE_EXAMPLE_SMOKE_OK`

### Run all tests

```bash
python -m pytest -q
```

725+ tests covering orchestration, safety gates, recovery, and evidence pipelines — all deterministic, all provider-free.

## CLI Overview

Feiyue ships with the `feiyue-runs` command for evidence inspection and approval-gated operations:

| Command | Purpose |
|---|---|
| `feiyue-runs list` | List persisted run evidence |
| `feiyue-runs show <task_id>` | Inspect a run's full evidence |
| `feiyue-runs handoff <task_id>` | Render a fallback handoff summary |
| `feiyue-runs capability-history` | Build longitudinal capability history |
| `feiyue-runs longitudinal-gain` | Measure before/after improvement over time |
| `feiyue-runs review-inbox` | List pending review items (read-only) |
| `feiyue-runs curator-live-proposal` | Build asset proposal from verified evidence |
| `feiyue-runs promote-curator-asset` | Promote a reviewed asset with rollback evidence |

Additional commands for asset-reuse smoke, creative-to-execution E2E, multi-student dry-run, and export are documented in the [CLI Reference](docs/cli-reference.md).

## Documentation

- [Architecture](docs/architecture.md) — System flow, roles, evidence surfaces
- [Operator Guide](docs/operator-guide.md) — Daily operations and evidence inspection
- [CLI Reference](docs/cli-reference.md) — Complete command reference
- [Security Boundaries](docs/security-boundaries.md) — Authorization rules and safety defaults
- [Release Checklist](docs/release-checklist.md) — CI gates and verification requirements
- [Approval Runbooks](docs/approval-runbooks.md) — Authorization procedures for promotions and routing
- [Rollback Guide](docs/rollback-guide.md) — Safe rollback procedures
- [Resilient Session Runtime](docs/resilient-session-runtime.md) — Anti-amnesia recovery design
- [Live Smoke Playbook](docs/live-smoke-playbook.md) — Smoke testing checklist
- [Contributing](CONTRIBUTING.md) — Development conventions and CI expectations

## Development

Feiyue was built iteratively, starting from provider-free safety foundations through real-profile integration, creative-to-execution workflows, longitudinal measurement, and deployment readiness. The development process follows these principles:

- **Provider-free by default** — All core tests and CI pass deterministically without network access or API credentials
- **Evidence-first** — Every operation produces typed, persisted evidence that serves as the audit trail
- **TDD** — Red-green-refactor for all behavior changes
- **No secrets in code** — Provider credentials are never checked into the repository

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
