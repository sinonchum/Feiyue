# True Multi-Student Planner Design

## Purpose

4A productized the current real multi-profile lane as **one student + teacher retry**: a selected worker runs, a teacher may guide after verifier failure, and the worker retries under exact authorization. This is not yet true parallel multi-student execution.

4C defines the next product boundary for a **true multi-student planner** that can select and authorize multiple student workers for one task while keeping Feiyue's dry-run, verifier-gated, no-promotion safety model.

## Current state

- `MultiWorkerOrchestrationPlanner` reads project-local routing evidence and `.hermes/model-routing.yaml`.
- `MultiWorkerRouter._select_workers(...)` currently returns at most one student worker.
- `MultiWorkerWorkflowDryRunOrchestrator` executes one selected worker, optionally with teacher escalation and retry.
- `run-approved-multi-worker-teacher-retry` now productizes the real worker + teacher + retry path with three exact provider run records.

## Target state

A true multi-student planner should produce route plans with multiple student workers when the task can be decomposed into independent lanes. Example lanes:

- implementation worker
- test worker
- docs/review worker
- verifier/merge-review worker

Each selected worker must have a declared responsibility, allowed file scope, max profile calls, and independent exact authorization.

## Proposed evidence model

Add a new plan shape or extension fields:

- `worker_assignments`: list of assignment objects
  - `assignment_id`
  - `profile_id`
  - `role`: implementation | tests | docs | review | verifier
  - `capabilities`
  - `allowed_files`
  - `max_profile_calls`
  - `depends_on_assignment_ids`
- `merge_strategy`: reject_on_conflict | ordered_overlay | reviewer_selected_patch
- `verifier_strategy`: per_assignment_then_combined | combined_only
- `dry_run_only: true`
- `promotion_attempted: false`
- `global_hermes_config_mutated: false`

## Authorization contract

The approval must bind:

- `plan_id`
- `task_id`
- exact `worker_assignments` hash
- exact `worker_profile_ids`
- exact `allowed_files` per worker
- `merge_strategy`
- `verifier_strategy`
- `dry_run_only: true`
- max total profile calls

Missing or mismatched approval must block before provider calls.

## Execution model

1. Build assignment prompts from the plan.
2. Execute independent workers in a deterministic order for the first productized slice, even if the model is conceptually parallel.
3. Parse each worker's candidate writes.
4. Validate allowed file scope per worker.
5. Apply candidate writes into isolated sandbox worktrees.
6. Run per-assignment verifier when configured.
7. Merge candidate writes using the approved merge strategy.
8. Run combined verifier.
9. Persist evidence under `.hermes/multi-student-workflows/<run_id>/`.

## Merge strategy

The first implementation should use `reject_on_conflict`:

- If two workers write the same path, block unless a reviewer/merge worker is explicitly assigned.
- If patches touch disjoint files, combine them in deterministic assignment order.
- If combined verifier fails, keep all worker outputs and failure dossiers, but do not promote.

Future strategies may include reviewer-selected patch or teacher-guided merge repair, but those need separate approval gates.

## Safety boundaries

- `promotion remains out of scope` for the first true multi-student slice.
- No PR creation, merge, deployment, or production mutation.
- No global Hermes config mutation.
- Source checkout must remain clean.
- All real profile calls require exact `AuthorizedProviderRunRecord` evidence.
- Teacher or reviewer intervention requires separate exact authorization.

## TDD entry plan

1. RED: planner can emit two worker assignments from routing table primary/fallback when task declares two independent capabilities.
2. RED: approval hash mismatch blocks before provider calls.
3. RED: two fake workers writing disjoint files merge and verify.
4. RED: two fake workers writing same file block with conflict evidence.
5. GREEN: implement assignment model and deterministic sequential executor.
6. GREEN: add CLI inspection only after SDK tests pass.
7. Smoke: run on Feiyue real repo with fake workers first, then one real worker plus one fake worker, before any all-real multi-student run.

## Acceptance criteria

- Multiple student workers appear in evidence as distinct assignments, not as teacher retry events.
- Each assignment records profile, prompt source, candidate writes, verifier result, and scope validation.
- Combined workflow report records merge strategy and conflict status.
- Source checkout clean after every run.
- `dry_run_only: true`, `promotion_attempted: false`, and `global_hermes_config_mutated: false` remain invariant.
