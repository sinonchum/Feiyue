# Phase 1–3 Core Runtime Implementation Plan

> **For Hermes:** Implement with strict TDD. Write failing tests before production code, run them to verify RED, then implement minimal code and verify GREEN.

**Goal:** Build the first runnable Feiyue core package: stable schemas plus the first recovery-runtime data contracts that prevent model-switch amnesia.

**Architecture:** Start with a Python package under `packages/feiyue-core`. Keep code dependency-light: Pydantic models, enum-based statuses, JSON serialization helpers, and tests. No live LLM/provider calls in this phase.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, pyproject workspace package.

---

## Scope for this first development slice

This slice intentionally covers the smallest useful foundation from the development outline:

1. Package skeleton for `feiyue-core`.
2. Phase 1 schema models:
   - `TaskSpec`
   - `Candidate`
   - `ExecutionRun`
   - `VerificationResult`
   - `StrategyVersion`
   - `SkillCandidate`
   - `TraceEvent`
3. Phase 3 recovery data contracts:
   - `RecoveryManifest`
   - `OperationRecord`
   - `KnownMistake`
4. JSON serialization/deserialization tests.
5. Minimal README usage update.

Out of scope for this slice:

- FastAPI backend.
- Real sandbox execution.
- LLM provider adapters.
- GitHub side-effect reconciliation implementation.
- Dashboard.

---

## Task 1: Create package skeleton and failing schema tests

**Objective:** Establish the package layout and tests that describe the desired schema behavior before implementation.

**Files:**

- Create: `packages/feiyue-core/pyproject.toml`
- Create: `packages/feiyue-core/feiyue_core/__init__.py`
- Create: `packages/feiyue-core/feiyue_core/schemas/__init__.py`
- Create: `packages/feiyue-core/feiyue_core/recovery/__init__.py`
- Create: `packages/feiyue-core/tests/test_schemas.py`
- Create: `packages/feiyue-core/tests/test_recovery_contracts.py`

**RED verification:**

Run:

```bash
cd packages/feiyue-core
python3 -m pytest tests/test_schemas.py tests/test_recovery_contracts.py -q
```

Expected: fail because schema modules do not exist or models are not implemented.

---

## Task 2: Implement minimal Phase 1 schemas

**Objective:** Implement the smallest Pydantic models that satisfy serialization, status, and metadata tests.

**Files:**

- Create: `feiyue_core/schemas/common.py`
- Create: `feiyue_core/schemas/task.py`
- Create: `feiyue_core/schemas/candidate.py`
- Create: `feiyue_core/schemas/execution.py`
- Create: `feiyue_core/schemas/verification.py`
- Create: `feiyue_core/schemas/strategy.py`
- Create: `feiyue_core/schemas/skill.py`
- Create: `feiyue_core/schemas/trace.py`
- Modify: `feiyue_core/schemas/__init__.py`

**GREEN verification:**

Run:

```bash
cd packages/feiyue-core
python3 -m pytest tests/test_schemas.py -q
```

Expected: pass.

---

## Task 3: Implement recovery data contracts

**Objective:** Implement manifest, operation record, and known mistake models that directly address fallback/断电/断网失忆 prevention.

**Files:**

- Create: `feiyue_core/recovery/manifest.py`
- Create: `feiyue_core/recovery/operation_record.py`
- Create: `feiyue_core/recovery/known_mistakes.py`
- Modify: `feiyue_core/recovery/__init__.py`

**GREEN verification:**

Run:

```bash
cd packages/feiyue-core
python3 -m pytest tests/test_recovery_contracts.py -q
```

Expected: pass.

---

## Task 4: Full local quality gate

**Objective:** Ensure all current tests pass and package can be imported.

Run:

```bash
cd packages/feiyue-core
python3 -m pytest tests/ -q
python3 -c "import feiyue_core; print(feiyue_core.__version__)"
```

Expected: tests pass and version prints.

---

## Task 5: Documentation and commit

**Objective:** Document the first runnable development slice and push it.

**Files:**

- Modify: `README.md`
- Possibly modify: `.gitignore` if new local-only runtime dirs are needed.

**Verification:**

```bash
git status --short
git diff --stat
git add README.md docs/plans/phase-1-core-runtime-plan.md packages/feiyue-core
git commit -m "feat: add Feiyue core schema package"
git push origin main
git status --short --branch
git ls-remote origin refs/heads/main
```

---

## Implementation rules

- Strict TDD: tests first, verify RED, implement, verify GREEN.
- No live provider calls.
- No model/provider config changes.
- No broad `git add .`; stage exact paths.
- Keep schemas small and stable.
- Do not add runtime side effects yet; only data contracts.
