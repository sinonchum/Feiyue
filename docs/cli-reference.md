# Feiyue CLI Reference

Generated from the productized `feiyue-runs` command registry.

## Safety defaults

- Provider-free and read-only commands are the default inspection path.
- Approval-gated commands require exact persisted approvals before any state mutation.
- Draft PR, release-candidate, and production-promotion commands are fail-closed and local-only unless a separate adapter is explicitly authorized.
- No command in this reference requires secrets to be written into docs.

## Core evidence inspection

- `feiyue-runs list [--json]` — List persisted run evidence or emit catalog JSON.
- `feiyue-runs show <task_id>` — Print one run-evidence.json payload.
- `feiyue-runs handoff <task_id>` — Render a compact fallback handoff summary.
- `feiyue-runs review-inbox` — List pending local review items without mutating state.
- `feiyue-runs semantic-review --review-id <id> --artifact-id <id> --artifact-path <path>` — Run the provider-free semantic reviewer and optionally write audit evidence.
- `feiyue-runs creative-metrics-record --proposal-id <id> --seed-id <id> --decision <accepted|rejected|deferred>` — Record human creative proposal acceptance/taste metrics without provider calls.
- `feiyue-runs workflow-smoke <run_id>` — Inspect real-profile workflow dry-run evidence.
- `feiyue-runs workflow-promotion <run_id>` — Inspect approval-gated workflow promotion evidence.
- `feiyue-runs live-profile-matrix <run_id>` — Inspect retained Phase C live profile matrix summary evidence.
- `feiyue-runs controlled-teacher-escalation <run_id>` — Inspect retained controlled teacher-escalation summary evidence.

## Capability and learning loop

- `feiyue-runs capability-history [--write-report]` — Collect workflow evidence into longitudinal capability history.
- `feiyue-runs longitudinal-gain [--min-samples N] [--window-size N] [--write-report]` — Evaluate before/after gains from capability history.
- `feiyue-runs longitudinal-mini-program --run-id <id> [--write-report]` — Run a provider-free 3-batch mini-program that measures lesson/template/routing improvement.
- `feiyue-runs asset-reuse-smoke --run-id <id> --lesson-path <path> [--write-report]` — Run provider-free promoted lesson reuse evidence.
- `feiyue-runs curator-live-proposal --run-id <id> --proposal-id <id> [--write-proposal]` — Build a review-required asset proposal from verified live evidence.
- `feiyue-runs promote-curator-asset --proposal-id <id> --reviewer <name> --reason <text> --rollback-ref <ref> --patch-id <id>` — Promote one approved project-local asset patch with rollback evidence.

## Multi-worker and real-profile dry runs

- `feiyue-runs multi-worker-plan --plan-id <id> --task-id <id> --capability <name>` — Create a provider-free multi-worker route plan.
- `feiyue-runs approve-multi-worker-dry-run --plan-id <id> --approved-by <name> --approval-id <id> --reason <text>` — Create exact approval evidence for a multi-worker dry-run plan.
- `feiyue-runs run-approved-multi-worker-dry-run --plan-id <id> --run-id <id> --profile-runner fake|hermes ...` — Run an approved selected-worker dry-run.
- `feiyue-runs run-approved-multi-worker-teacher-retry --plan-id <id> --run-id <id> --worker-initial-run-record <json> --teacher-run-record <json> --worker-retry-run-record <json>` — Run an approved worker+teacher+retry dry-run using three exact provider run records.
- `feiyue-runs approve-true-multi-student-dry-run --plan-path <json> --approved-by <name> --approval-id <id>` — Create exact approval evidence for a true multi-student dry-run plan.
- `feiyue-runs run-approved-true-multi-student-dry-run --plan-id <id> --run-id <id> --fake-response profile=json` — Run an approved true multi-student fake-first dry-run.
- `feiyue-runs true-multi-student-workflow <run_id>` — Inspect true multi-student workflow evidence.
- `feiyue-runs real-multi-worker-live-dry-run --authorization-path <path> --plan-id <id> --run-id <id> ...` — Run an explicitly authorized real multi-worker live dry-run seam.

## Approval-gated operations

- `feiyue-runs approve-promotion <run_id> ...` — Create exact approval evidence for a verified workflow dry-run.
- `feiyue-runs promote-approved <run_id> --commit-message <text>` — Promote a dry-run using persisted approval evidence.
- `feiyue-runs draft-pr-plan <run_id> --allowed-target-branch <branch>` — Create a local-only draft PR plan from verified promotion evidence.
- `feiyue-runs approve-draft-pr <run_id> --approved-by <name> --approval-id <id> --reason <text>` — Create exact approval evidence for fake-first draft PR creation.
- `feiyue-runs create-approved-draft-pr <run_id> --adapter fake|github` — Create exact-approved draft PR evidence; github mode opens a draft PR only.
- `feiyue-runs release-candidate-plan <release_id> --run-id <id> --allowed-target-branch <branch> --ci-evidence-path <path> --post-promotion-verification-command <cmd>` — Create a fail-closed local-only release-candidate plan.
- `feiyue-runs approve-production-promotion <release_id> --approved-by <user> --approval-id <id> --reason <text>` — Create exact approval evidence for production-promotion readiness.
- `feiyue-runs verify-production-promotion-readiness <release_id>` — Verify production-promotion readiness without mutating production.
- `feiyue-runs merge-rollback-deploy-readiness-plan <readiness_id> --merge-readiness-evidence-path <path> --rollback-command <cmd> --deploy-step <step> --post-merge-verification-command <cmd>` — Create explicit merge/rollback/deploy readiness design evidence without executing merge/deploy.
- `feiyue-runs approve-merge-rollback-deploy-readiness <readiness_id> --approved-by <user> --approval-id <id> --reason <text>` — Create exact approval for merge/rollback/deploy readiness design only.
- `feiyue-runs verify-merge-rollback-deploy-readiness <readiness_id>` — Verify approved merge/rollback/deploy readiness without merge/deploy side effects.
- `feiyue-runs approve-merge-execution <readiness_id> --approved-by <user> --approval-id <id> --reason <text>` — Create exact approval for 8B approved merge execution.
- `feiyue-runs execute-approved-merge <readiness_id> --adapter fake|github` — Execute an approved merge through a fail-closed adapter; fake adapter simulates only.
- `feiyue-runs approve-pr-ready-for-review <readiness_id> --approved-by <user> --approval-id <id> --reason <text>` — Create exact approval for 8C PR ready-for-review transition.
- `feiyue-runs transition-pr-ready-for-review <readiness_id> --adapter fake|github` — Transition an approved PR ready-for-review through a fail-closed adapter; fake adapter simulates only.
- `feiyue-runs approve-pr-ready-for-review-external-mutation <readiness_id> --approved-by <user> --approval-id <id> --reason <text>` — Create exact approval for the real GitHub Draft-to-ready PR mutation only.
- `feiyue-runs transition-pr-ready-for-review <readiness_id> --adapter github --perform-external-mutation` — Perform the exact-approved GitHub Draft-to-ready PR mutation only; no merge/deploy.
