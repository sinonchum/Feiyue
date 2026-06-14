# Real multi-worker live dry-run evidence seam

Wave5-3 adds a dry-run-only evidence seam for explicitly authorized real Hermes multi-worker runs. It is fake-first for tests and fail-closed before any profile/provider call unless an exact local authorization is supplied.

## CLI

```bash
python3 -m feiyue_core.workflow.runs_cli --root <project-root> \
  real-multi-worker-live-dry-run \
  --plan-id <multi-worker-plan-id> \
  --run-id <run-id> \
  --source-repo <git-repo> \
  --project-name <name> \
  --task-id <task-id> \
  --title <title> \
  --scope <scope> \
  --file-to-modify <path> \
  --verification-command "python -m pytest -q" \
  --authorization-path <authorization.json> \
  --profile-runner fake \
  --fake-worker-response-json '{"writes": []}'
```

For an operator-approved Hermes seam, use `--profile-runner hermes --hermes-run-record <AuthorizedProviderRunRecord.json>`. Tests do not make real Hermes/profile calls.

## Evidence and safety defaults

Evidence is persisted at:

```text
.hermes/real-multi-worker-runs/<run_id>/evidence.json
```

The persisted record is capability-history compatible and includes `provider_call_count`, `cost_usd`, `latency_ms`, `source_clean`, `dry_run_only: true`, `global_hermes_config_mutated: false`, and `promotion_attempted: false`.

Required local authorization must exactly match plan id, run id, task id, selected worker profile, action `execute_real_multi_worker_live_dry_run`, scope `real_multi_worker_live_dry_run_execute`, `dry_run_only: true`, and promotion disabled. Teacher escalation uses a separate optional authorization with action `execute_real_multi_worker_teacher_escalation_dry_run` and scope `real_multi_worker_teacher_escalation`.
