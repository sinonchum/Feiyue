# Contributing to Feiyue

Feiyue is currently a provider-free foundation for a Hermes-based Creative Evolution Loop Orchestrator. Contributions should preserve deterministic tests, recovery evidence, and clear authorization boundaries.

## Development Rules

- Use RED-GREEN-REFACTOR for behavior changes.
- Keep new features provider-free by default.
- No real provider credentials in code, tests, docs, fixtures, traces, or examples.
- Do not mutate Hermes configuration unless the user explicitly authorizes that specific change.
- Prefer typed models, deterministic fixtures, and machine-readable reports over narrative-only behavior.
- Keep examples small, reproducible, and no-network.

## Required Local Commands

Use the active Python environment from `packages/feiyue-core`.

Terminal: `"python -m pytest -q"`

For release-quality changes also run:

```bash
python -m compileall -q feiyue_core
python -m pytest -q
```

From repository root:

```bash
git diff --check
```

Run the secret scan from `docs/release-checklist.md` before committing.

## TDD Expectations

1. Write the failing test first.
2. Run the targeted test and confirm it fails for the expected missing behavior.
3. Implement the smallest provider-free change.
4. Run the targeted test and then the full suite.
5. Update docs only after real command output is known.

Do not add production behavior and then retrofit tests after the fact.

## Provider and Secret Boundaries

No real provider credentials means:

- no API keys;
- no bearer tokens;
- no OAuth secrets;
- no passwords;
- no connection strings;
- no realistic fake secrets that trip scanners.

If a future task requires real provider integration, it must be separately authorized and isolated behind explicit fake-provider tests first.

## GitHub / CI Expectations

- Keep `.github/workflows/ci.yml` as an orchestrator for existing commands, not a second implementation.
- Add contract tests when adding CI behavior.
- Wait for remote GitHub Actions success before reporting CI complete.

## Documentation Expectations

Documentation should clearly label:

- what is provider-free and complete;
- what is only a foundation;
- what is gated on explicit authorization;
- which commands reproduce the evidence.
