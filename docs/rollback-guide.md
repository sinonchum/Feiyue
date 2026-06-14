# Feiyue Rollback Guide

Rollback is an evidence-backed procedure, not a best-effort note. Any approved promotion must leave enough rollback evidence to restore or simulate restore before a production PR is considered.

## Required rollback evidence

For a workflow promotion, collect:

- `.hermes/workflow-promotions/<run_id>/promotion-evidence.json`
- `.hermes/promotion-lifecycle/<run_id>/rollback-evidence.json` when a sandbox rollback simulation is run
- target branch
- promoted commit
- rollback ref
- changed files
- verifier command and exit code
- reason codes for any failed rollback simulation

Do not proceed to remote or production PR activity if the rollback ref is missing.

## Inspect promotion evidence

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. workflow-promotion <run_id>
git show --stat --oneline --decorate HEAD
git status --short
```

Confirm the promotion evidence references the exact approved run and changed files. Confirm no global Hermes config mutation occurred and no unexpected files changed.

## Simulate rollback locally

The current rollback simulation API is local-only and does not push, open PRs, call providers, or mutate Hermes global config. Use this Python one-liner only after promotion evidence exists:

```bash
cd packages/feiyue-core
python3 - <<'PY'
from pathlib import Path
from feiyue_core.workflow import simulate_rollback_sandbox

result = simulate_rollback_sandbox(
    root=Path('../..').resolve(),
    run_id='<run_id>',
    verifier_command='python3 -m pytest packages/feiyue-core/tests/test_docs_release_contract.py -q',
)
print(result.model_dump_json(indent=2))
PY
```

Expected output includes a persisted rollback evidence file under `.hermes/promotion-lifecycle/<run_id>/rollback-evidence.json` and a clear `rolled_back`/status result. Treat any missing `rollback_ref`, missing target branch, verifier failure, or sandbox setup failure as a blocker.

## Emergency local rollback

If a local promotion must be reverted before a remote PR exists:

```bash
git status --short
git branch --show-current
git log --oneline -5
# After verifying the rollback ref from promotion evidence:
git reset --hard <rollback_ref>
python3 -m pytest packages/feiyue-core/tests/test_docs_release_contract.py -q
```

Only use `git reset --hard` after confirming all uncommitted operator work is disposable or backed up. Do not reset a shared or production branch without explicit human authorization.

## Stop conditions

Stop and preserve evidence if:

- rollback evidence is missing or inconsistent
- verifier command fails after rollback
- changed files differ from approval evidence
- `dry_run_only: true` was not present in source evidence
- production PR/promotion disabled by default was bypassed
- review inbox read-only behavior is violated
