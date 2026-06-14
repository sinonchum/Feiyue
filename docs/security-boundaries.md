# Feiyue Security Boundaries

Feiyue operator workflows are designed to fail closed. This document defines boundaries that apply to docs, dry runs, approvals, live/profile smoke preparation, routing, and rollback.

## Forbidden without explicit human authorization

- Real provider/profile execution.
- Changing global Hermes configuration or profile configuration.
- Reading, printing, copying, or committing provider credentials.
- Increasing provider/profile call budgets.
- Applying routing changes.
- Promoting candidate writes.
- Creating production PRs, pushing branches, or touching remotes.

## Always forbidden in these runbooks

- no global Hermes config mutation
- no secrets in command examples, prompts, approval reasons, evidence summaries, or docs
- no broad approvals such as "approve all future runs"
- no provider calls from docs tests
- no live smoke execution as part of documentation coverage

## Required safety phrases and fields

Operators and tests should look for these exact phrases/fields in docs and evidence:

- `dry_run_only: true`
- `promotion_attempted: false`
- `global_hermes_config_mutated: false`
- `provider_execution_requested: false`
- `routing_table_mutated: false`
- exact authorization
- production PR/promotion disabled by default
- rollback evidence
- review inbox read-only

## Review inbox boundary

The review inbox is an audit surface only:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. review-inbox --format json
```

It may read `.hermes` evidence and summarize pending items. It must not write approval files, promote branches, apply routing, execute providers, or mutate Hermes profile/global configuration.

## Evidence redaction boundary

Before sharing evidence outside the local operator context:

- Confirm stdout/stderr are redacted.
- Remove environment values, tokens, cookies, API keys, and machine-local secrets.
- Prefer hashes, run ids, commit ids, and relative evidence paths over raw logs.
- Do not paste secrets into approval reasons.

## Promotion boundary

Promotion requires separate exact approval after a dry run. Even after approval, the operator must verify rollback evidence exists or can be produced. If rollback evidence is absent, incomplete, or failing, stop before any remote or production PR action.
