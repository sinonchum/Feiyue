# Wave 9 Real Multi-worker Project Slice Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Turn the post-merge/no-deploy release handoff into the next executable blueprint phase: a real multi-worker project slice that proves multiple Hermes profiles can collaborate on a small real task while verifier evidence, review gates, and promotion/deploy safety remain explicit and fail-closed.

**Architecture:** Wave 9 is an evidence-first, no-deploy phase. It reuses the existing true multi-student dry-run, real profile authorization, workflow verification, capability-history ingestion, review inbox, and release-candidate gates. The first slice must stay dry-run-only; branch/PR/promotion/deploy paths are separate later approvals.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, Git worktree, Hermes profile subprocess runner, JSON evidence under `.hermes/`, GitHub Actions CI, no production deployment.

---

## 8H Planning Judgment

Wave 8 is complete through the safe post-merge handoff:

- PR #3 is merged.
- 8G handoff evidence is `handoff_ready`.
- CI is green.
- Current verified local baseline is `658 passed`.
- Deploy and production mutation are still `false`.

The master blueprint says the next frontier is not another release gate. The next useful proof is **M10/M11 continuation**: a real multi-worker project slice that exercises actual role separation on a small real task while keeping all mutation paths gated.

## Wave 9 Scope

Wave 9 should answer:

> Can Feiyue assign a small real project task to multiple authorized Hermes profiles, merge their candidate outputs safely in a sandbox, run deterministic verifiers, produce reviewable evidence, and update capability/evaluation records without touching production or bypassing approval gates?

## Non-goals / Safety Boundaries

Wave 9 does **not** automatically do any of these:

- deploy
- production promotion
- auto-merge
- global Hermes config mutation
- unapproved provider calls
- unapproved GitHub PR creation
- unapproved branch promotion
- production_mutated: true evidence or any production mutation without separate exact approval

Every external side effect remains separately exact-approved; Wave 9 defaults to production_mutated: false.

---

## Wave 9 Milestones

### Wave9-1: Planning Evidence and Contracts

**Objective:** Lock the Wave 9 scope, safety boundaries, acceptance gates, and next executable slice in docs/tests.

**Files:**

- Create: `docs/plans/wave9-real-multi-worker-project-slice-plan.md`
- Modify: `docs/Feiyue-self-evolution-development-outline.md`
- Modify: `README.md`
- Modify: `packages/feiyue-core/tests/test_docs_release_contract.py`

**Functional Acceptance:**

- Plan states Wave 9 scope and non-goals.
- Plan names the first executable slice: Wave9-2.
- Docs contract asserts no-deploy/no-production-mutation boundaries.
- Full tests pass.

**Quality Acceptance:**

- No credentials, provider keys, or local-only secrets.
- No actual provider call required.
- No external side effect.

### Wave9-2: Real Multi-worker Task Pack

**Objective:** Create a typed task pack for one small real Feiyue project task, with two or more worker assignments, explicit file scopes, verifier commands, conflict policy, and review criteria.

**Files:**

- Create or extend: `feiyue_core/workflow/multi_student_task_pack.py`
- Test: `tests/test_multi_student_task_pack.py`
- Evidence root: `.hermes/wave9-task-packs/<task_pack_id>/task-pack.json`

**TDD Steps:**

1. Write RED test for missing assignment scope blocked.
2. Write RED test for overlapping file scopes requiring explicit conflict policy.
3. Implement `MultiStudentTaskPack` and writer/reader.
4. Verify task pack is provider-free and dry-run-only.

**Functional Acceptance:**

- Task pack binds `task_pack_id`, `task_id`, assignment scopes, worker profile ids, verifier commands, conflict policy, and `dry_run_only: true`.
- Task pack writes machine-readable evidence.
- No worker execution happens in Wave9-2.

### Wave9-3: Exact Authorization for Real Multi-worker Execution

**Objective:** Create an approval gate for executing the Wave9-2 task pack with real Hermes profiles.

**Files:**

- Extend: existing real/multi-student authorization module, or create `feiyue_core/workflow/wave9_authorization.py`
- Extend CLI: `feiyue-runs approve-wave9-real-multi-worker-run`
- Test: `tests/test_wave9_real_multi_worker.py`

**Functional Acceptance:**

- Authorization binds task pack hash, worker profile ids, verifier commands, conflict policy, and `dry_run_only: true`.
- Missing/mismatched authorization blocks.
- Authorization evidence persists locally.

**Safety Acceptance:**

- No provider call when authorization is missing or mismatched.
- No promotion, PR, merge, deploy, or production mutation.

### Wave9-4: Real Multi-worker Dry-run Execution Smoke

**Objective:** Run the authorized task pack with at least two configured Hermes profiles on a tiny real Feiyue task.

**Files:**

- Extend: existing true multi-student dry-run executor / CLI
- Evidence root: `.hermes/wave9-real-multi-worker-runs/<run_id>/`
- Tests: fake-runner TDD first; real smoke only after explicit authorization.

**Functional Acceptance:**

- At least two worker assignments are invoked according to exact authorization.
- Combined candidate output is sandboxed.
- Verifier commands decide success/failure.
- Evidence records provider_call_count, assignment results, conflict_files, verifier results, and combined status.

**Safety Acceptance:**

- `dry_run_only: true`
- `promotion_attempted: false`
- `global_hermes_config_mutated: false`
- source checkout clean after run

### Wave9-5: Review Inbox and Capability/Evaluation Ingestion

**Objective:** Convert Wave9-4 evidence into reviewable artifacts and capability/evaluation records.

**Files:**

- Extend review inbox evidence surfaces.
- Extend capability-history ingestion if needed.
- Extend strategy/evaluation comparison if needed.

**Functional Acceptance:**

- Review inbox shows assignment-level outputs, verifier results, conflicts, and next safe actions.
- Capability-history records distinguish worker success, conflict, verifier failure, and teacher escalation.
- Strategy/evaluation record can compare single-worker vs multi-worker outcomes when both exist.

### Wave9-6: Optional Branch / PR Promotion Planning Only

**Objective:** If Wave9-4 succeeds and human review approves, produce a branch/PR readiness plan, not an automatic PR or merge.

**Functional Acceptance:**

- Emits readiness plan with rollback and verification commands.
- Requires separate exact approval before any real branch promotion or GitHub PR creation.

**Safety Acceptance:**

- No auto-merge.
- No deploy.
- No production mutation.

---

## Immediate Next Slice

Run **Wave9-1** now as the planning/status-contract slice, then proceed to **Wave9-2 Task Pack**.

Wave9-2 is the best next implementation slice because it is:

- safe and provider-free;
- directly aligned with M10/M11 blueprint gaps;
- prerequisite for real multi-worker execution;
- narrow enough for TDD;
- useful even before any real provider call.

## Verification Commands for Wave9-1

Run from `packages/feiyue-core`:

- `python -m pytest tests/test_docs_release_contract.py::test_status_docs_capture_8h_wave9_planning -q`
- `python -m pytest -q`
- `python -m compileall -q feiyue_core`
- `git diff --check`
- secret scan

## Wave 9 Exit Criteria

Wave 9 is complete only when:

1. a real multi-worker task pack is exact-authorized;
2. at least two real Hermes profiles execute assigned scopes in dry-run mode;
3. sandbox verifier evidence determines outcome;
4. review inbox/capability/evaluation artifacts are generated;
5. source checkout remains clean;
6. promotion/PR/merge/deploy are still separate exact-approved operations.
