# Feiyue Docs

This index is a static documentation stub for the provider-free Feiyue foundation. It links the canonical blueprint, system doctrine, architecture, release gates, contribution rules, and local smoke surfaces without relying on external assets or provider credentials.

## Canonical Direction

- [Master Blueprint](Feiyue-master-blueprint.md) — human creativity, strong-model specification, weak-model execution, verification, teacher-guided repair, distillation, and capability expansion.
- [System Doctrine](Feiyue-system-doctrine.md) — student/teacher roles, sparse intervention, quality preservation, and self-evolution principles.
- [Self-Evolution Development Outline](Feiyue-self-evolution-development-outline.md) — current wave plan, completed assets, and acceptance gates.
- [Product Requirements](Feiyue-PRD.md) — requirements for verifiable feedback-driven self-improvement.

## Architecture and Release Surfaces

- [Architecture](architecture.md) — provider-free system flow, role boundaries, evidence surfaces, and gated future work.
- [Static architecture diagram](assets/feiyue-architecture.svg) — flat SVG diagram of the human-to-curator workflow.
- [Release Checklist](release-checklist.md) — local verification commands, CI gates, secret scan, and authorization boundaries.
- [CLI Reference](cli-reference.md) — stable `feiyue-runs` commands for evidence inspection, approval-gated operations, semantic review, and creative metrics.
- [Operator Guide](operator-guide.md) — daily operator checks, evidence locations, no global Hermes config mutation, and dry-run defaults.
- [Approval Runbooks](approval-runbooks.md) — exact authorization commands for workflow promotion, routing apply, and multi-worker dry-run approvals.
- [Live Smoke Playbook](live-smoke-playbook.md) — provider-free rehearsal, live/profile smoke authorization checklist, and abort gates.
- [Security Boundaries](security-boundaries.md) — forbidden actions, review inbox read-only behavior, secret handling, and production PR/promotion disabled by default.
- [Rollback Guide](rollback-guide.md) — rollback evidence requirements, local rollback simulation, and stop conditions.
- [Real Provider Integration Plan](real-provider-integration-plan.md) — plan-only authorization sequence, forbidden actions, no global Hermes config mutation, auditable evidence, and rollback/abort gates for future real provider execution.
- [Contributing Guide](../CONTRIBUTING.md) — TDD, provider-free defaults, secret handling, and CI expectations.

## Provider-Free Examples and Benchmarks

These smoke surfaces are documented as local commands and expected markers. They do not require network access, real provider credentials, or Hermes profile mutation.

- [README provider-free example smoke](../README.md#implementation) — runs `feiyue_core.examples.provider_free_smoke` and expects `PROVIDER_FREE_EXAMPLE_SMOKE_OK`.
- [README provider-free benchmark smoke](../README.md#implementation) — runs `feiyue_core.evaluation.benchmark_runner --quick` and expects `BENCHMARK_SMOKE_OK`.
- [Release checklist smoke gates](release-checklist.md) — records provider-free example smoke, provider-free benchmark smoke, static export-all, compileall, pytest, and secret scan requirements.

## Provider Boundaries

Real provider execution, Hermes profile scheduling, real weak/strong benchmark calls, and production promotion remain explicitly gated future work. Documentation changes in this lane are static and provider-free.
