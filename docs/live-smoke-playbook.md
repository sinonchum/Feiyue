# Feiyue Live Smoke Playbook

This playbook documents how to prepare and inspect a live/profile smoke. It is not blanket authorization. Do not execute live provider/profile calls unless a human has granted exact authorization for the named run, profiles, repository, call budget, and dry-run scope.

## Hard boundaries

- no global Hermes config mutation
- `dry_run_only: true`
- `promotion_attempted: false`
- production PR/promotion disabled by default
- exact authorization required before any real profile/provider call
- no secrets in prompts, command lines, evidence summaries, or logs

## Provider-free rehearsal first

Run the rehearsal commands before requesting live authorization:

```bash
cd packages/feiyue-core
python3 -m pytest tests/test_provider_free_example_smoke.py tests/test_live_benchmark_contract.py -q
python3 -m feiyue_core.examples.provider_free_smoke \
  --root /tmp/feiyue-provider-free-example \
  --out /tmp/feiyue-provider-free-example-report \
  --bundle /tmp/feiyue-provider-free-example-report.zip
python3 -m feiyue_core.evaluation.benchmark_runner \
  --quick \
  --output /tmp/feiyue-benchmark.json \
  --output-markdown /tmp/feiyue-benchmark.md
```

Expected markers: `PROVIDER_FREE_EXAMPLE_SMOKE_OK` and `BENCHMARK_SMOKE_OK`.

## Authorization request checklist

A live/profile smoke request must include:

- Run id and task id.
- Source repo path and target files.
- Worker profile and optional teacher profile.
- Maximum profile/provider call count.
- Confirmation that output must remain `dry_run_only: true`.
- Confirmation that production PR/promotion disabled by default applies.
- Evidence paths to be written under `.hermes/workflow-smokes/<run_id>/`.
- Rollback evidence expectations if later promotion is requested.

If any item is missing, stop. Do not improvise broader authorization.

## Inspect smoke evidence

After an authorized smoke has been run by the appropriate operator, inspect only local evidence:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. workflow-smoke <run_id>
python3 -m feiyue_core.workflow.runs_cli --root ../.. review-inbox --format json
```

Acceptable dry-run evidence contains:

- `status: verified` or an explicit blocked/needs-teacher status with reason codes.
- `dry_run_only: true`.
- `promotion_attempted: false`.
- Redacted stdout/stderr only.
- Provider call count at or below the authorized budget.

## Abort conditions

Abort and preserve evidence if:

- A command would read, print, copy, or commit credentials.
- A command would edit `~/.hermes` global/profile configuration.
- A command would push, open a production PR, or promote without exact approval.
- Evidence lacks `dry_run_only: true` or reports unexpected `promotion_attempted: true`.
- The profile/provider call count would exceed the authorized budget.

Record the abort reason in the run notes and keep the review inbox read-only until a new authorization is granted.
