---
name: feiyue-bridge
description: "Write Hermes session results into Feiyue Operator Console artifact structure. After each completed task on a Feiyue project, call the bridge to make results visible in the console."
version: 2.3.0
author: Simon
platforms: [windows, linux, macos]
---

# Feiyue Bridge — Lv 4 Self-Evolution

After completing work on any Feiyue project, call `feiyue-bridge.py` to write
the session result into the `.hermes/` artifact directory so the Feiyue
Operator Console can display it.

## Self-Evolution Loop (Lv 4)

The full loop:

```
① bridge --action self-evolve  → scan artifacts, propose improvement
② I execute the goal            → implement the change
③ bridge --action evolve         → write results back as Feiyue artifacts
④ Feiyue Console shows new evidence
⑤ GOTO ①
```

### Step 1: Analyze (lightweight model recommended)

```bash
python ~/AppData/Local/hermes/scripts/feiyue-bridge.py \
    --action self-evolve \
    --project-root <FEIYUE_PROJECT>
```

Reads all Feiyue artifacts, identifies gaps (missing evidence, blocked drafts,
pending intents, GC issues), picks the top priority proposal, writes a
session draft and review intent, and prints the goal.

**Best practice:** Use a lightweight/cheap model for the analysis/self-evolve step
(scanning artifacts, comparing code, identifying gaps) and the full model for
implementation. This follows the weak-model-for-analysis, strong-model-for-execution
pattern proven in VOYAGERAI Phase 2 (32-component gap analysis with cheap model).

**Enhanced self-evolve engine:** The engine now uses codebase-aware
dynamic analysis with 9 gap categories (A-I):

| Code | Gap | Detection method |
|------|-----|-----------------|
| A | checks_detail missing | Evidence files without `checks_detail` key |
| B | module evidence gap | Feature modules without matching evidence |
| C | low check count | Evidence files with only 1 check |
| D | pending real intents | Review intents not auto-generated from self-evolve |
| E | blocked drafts | Drafts with `blocked_until_exact_approval` status |
| F | stale/unapproved approvals | Approvals without real approved_by |
| G | broken server config | Missing config files |
| H | evidence drift | Evidence checks ≠ actual module state |
| I | stale execution output | Output older than 30m |

**Self-referential loop eliminated:** Previously, each `self-evolve` created
an intent for its own proposal, which the next cycle saw as "pending." The
enhanced engine tracks `evolved_categories` to avoid re-proposing the same
fix. Pending intents are now tagged `(0 real)` when self-referential,
so the real actionable proposals are always clearly identifiable.

**Prioritization:** Proposals are ranked by severity (🟡 medium > 🟢 low)
and filtered against already-evolved categories. The engine produces at
most 3 proposals per cycle, with the top-ranked one auto-drafted as
draft + intent.

### Step 2: Execute

Implement the proposed change using normal agent tools.

### Step 3: Write Results

```bash
python ~/AppData/Local/hermes/scripts/feiyue-bridge.py \
    --action evolve \
    --project-root <FEIYUE_PROJECT> \
    --draft-id <FROM_STEP_1> \
    --goal "<FROM_STEP_1>" \
    --toolsets file,terminal \
    --tool-call-count <N> \
    --checks <N> --passing <N>
```

Writes 4 artifacts at once: draft + evidence + intent + execution.

## Quick Reference

| Action | What it does |
|--------|-------------|
| `--action self-evolve` | Scan artifacts, analyze, propose top improvement, write draft+intent |
| `--action evolve` | One-shot: write draft + evidence + intent + execution (all 4) |
| `--action draft` | Write a Hermes session draft.json + events.json |
| `--action evidence` | Write frontend-dogfood evidence.json |
| `--action intent` | Write a review-intent-draft |
| `--action approval` | Write approval-gate approval.json + events + verifier-evidence |
| `--action execution` | Write execution-output output.json |
| `--action overview` | Print summary of all artifacts in the project |

## Common Parameters

| Param | Description |
|-------|-------------|
| `--project-root` | Feiyue project root (default: cwd) |
| `--draft-id` | Unique identifier; auto-generated if omitted |
| `--goal` | Task description (used in draft + evidence title) |
| `--toolsets` | Comma-separated toolset names |
| `--tool-call-count` | Number of tool calls during the session |
| `--checks` / `--passing` | Verification results |

### Draft→Approve→Execute pipeline can be exercised via API
The full approval lifecycle is: create session draft (`POST /api/hermes-session-drafts`) → auto-status `blocked_until_exact_approval` → approve (`POST .../{id}/approve-dry-run`) → auto-status `approved_dry_run` → execute (`POST .../{id}/execute-approved`) → replay events with `provider_call_count=0`. No Hermes startup needed. Use this for E2E Console validation without real provider calls.

### Real Hermes CLI Execution (Direction 1)
The Console "Execute real Hermes CLI" button triggers a real `subprocess.run(["hermes", "-z", goal])` instead of dry-run replay.

**Backend changes in `execution_output.py`:**
1. Import `subprocess` and `BaseModel`:
   ```python
   import subprocess
   from pydantic import BaseModel, Field
   ```
2. Change `ExecutionRequest` from `FeiyueModel` to `BaseModel`. The `FeiyueModel` base has `ConfigDict(extra="forbid")` which rejects new input fields at the Pydantic level:
   ```python
   class ExecutionRequest(BaseModel):
       executed_by: str = "operator"
       reason: str = "operator_executed_approved_dry_run"
       real_execution: bool = False
   ```
   (Alternatively, keep `FeiyueModel` and add `model_config = ConfigDict(extra="allow")` + import `ConfigDict`, but `BaseModel` is cleaner for simple input-only models.)
3. Add `real_execution: bool = False` to `ExecutionRequest`
4. In `execute_approved_dry_run()`: when `request.real_execution` is True, extract the draft goal from `events.json` first event message (strip `"Draft created for: "` prefix), then `subprocess.run(["hermes", "-z", goal], cwd=root, capture_output=True, text=True, timeout=600)`. Return `hermes_started=True, dry_run_only=False`.
5. The `ExecutionOutput` model and other output-only models can safely keep using `FeiyueModel` (they receive data from internal code, not external input).

**Frontend changes:**
1. `index.html`: Add `<button id="execute-real-hermes">▶ Execute real Hermes CLI</button>` in the session drafts panel
2. `app.js`: Add `executeFirstApprovedDraftReal()` function that POSTs to `/execute-approved` with `real_execution: true`
3. `renderHermesSessions()`: Enable/disable the new button alongside the existing dry-run button
4. `boot()`: Add `wireExecuteRealHermesButton()` call

The POST body: `{"executed_by":"feiyue-operator-console","reason":"g7_operator_executed_real_hermes","real_execution":true}`

### `checks_detail` evidence pattern
Bridge evidence files now support `checks_detail` — a dict of individual check names to boolean/numeric results. Add it to existing evidence.json files to enable richer Console display:

```json
{
  "checks": 5,
  "passing": 5,
  "checks_detail": {
    "status_aware_intents": true,
    "e2e_approval_pipeline": true,
    "approval_gate_created": true,
    "dry_run_verified": true,
    "execute_approved_tested": true
  }
}
```

The `_read_frontend_dogfood()` API handler passes `checks_detail` through to the Console response. The frontend `renderFrontendDogfood()` renders expandable detail rows for each check. Add or backfill `checks_detail` on existing evidence by patching the evidence.json directly, then trigger the bridge evolve cycle to close the loop.

### Frontend enhancements: status-aware intent display
The `renderReviewIntents()` function now shows a status breakdown line (`drafted=X · approved=Y · archived=Z`) with per-intent icons (✓ approved / 🗑 archived / 📝 drafted). The status-pill in the Console header auto-updates to reflect G-13 status-awareness. These patterns can be extended to other Console panels (drafts, executions) for consistent status visualization.

### Summary fields from aggregated list must be derived, not hardcoded
When a `list_*` function returns an aggregate model (e.g. `ExecutionOutputSummary` wrapping a list of `ExecutionOutput`), do NOT hardcode the summary fields:

```python
# ❌ WRONG — hides real data
return ExecutionOutputSummary(
    outputs=outputs,
    dry_run_only=True,        # always True even if individual outputs have real data
    hermes_started=False,     # always False
    provider_call_count=0,
)

# ✅ RIGHT — derive from the actual outputs
return ExecutionOutputSummary(
    outputs=outputs,
    dry_run_only=all(o.dry_run_only for o in outputs) if outputs else True,
    hermes_started=any(o.hermes_started for o in outputs),
    provider_call_count=sum(o.provider_call_count for o in outputs),
)
```

The same pattern applies to overview-level fields in `runs_api.py`: use `exec_summary.hermes_started` instead of hardcoded `False`.

### Pydantic model extension pitfall (critical)
When you manually edit intent.json/draft.json files to add new fields (e.g. `resolution`, `resolved_by`, `resolved_at` for lifecycle tracking), you MUST also add those fields as `str | None = None` to the corresponding Pydantic model. Both `ReviewIntentDraft` and `HermesSessionDraft` use strict Pydantic validation (`extra_forbidden`). If the fields aren't in the model, `list_review_intent_drafts()` / `list_hermes_session_drafts()` crash with `ValidationError`, which takes down the entire `GET /api/overview` endpoint (empty reply, HTTP 000).

**Fix:** Add the new fields to the Pydantic model class, then restart the server. With `uv pip install -e .`, source changes are picked up immediately — no reinstall needed, just restart the process.

```python
# In ReviewIntentDraft or HermesSessionDraft:
resolution: str | None = None
resolved_by: str | None = None
resolved_at: str | None = None
```

**Double-check server restart:** Even after adding fields to the model, an existing server process may still carry the cached module. If you get `extra_forbidden` errors after restart, try:
1. Kill the server process by real PID (from `netstat -ano | grep <PORT>`)
2. Delete `__pycache__` directories: `find packages/feiyue-core -name __pycache__ -type d -exec rm -rf {} +`
3. Set `PYTHONDONTWRITEBYTECODE=1` before starting the new server
4. If the `FeiyueModel` base has `ConfigDict(extra="forbid")`, override it in the specific model:
   ```python
   class MyRequest(FeiyueModel):
       new_field: bool = False
       model_config = ConfigDict(extra="allow")
   ```

### Windows server management: process lifecycle
On this Windows/MSYS host, `terminal(background=true)` wraps commands in `bash.exe`, so the returned PID is bash, NOT the python server. To find the actual server:

```bash
netstat -ano | grep '<PORT>' | grep LISTENING
# → TCP 127.0.0.1:<PORT> 0.0.0.0:0 LISTENING <REAL_PID>
taskkill //F //PID <REAL_PID>
```

**Python output buffering:** On Windows under git-bash, Python fully buffers stdout even in background processes. The process log may stay empty for minutes even though the server is running. Use `python -u` (`-u` flag) when starting background servers so startup messages appear in the process output immediately and `watch_patterns` can match.

**Zombie accumulation:** `process(action='kill')` only kills the bash wrapper, not the python child. Over multiple iterations, 5-10 zombie python.exe processes can accumulate on the same port. If a fresh server gives HTTP 000 (empty reply), check for old PIDs with `netstat -ano | grep LISTENING` and kill them by real PID. Using a fresh port (8897, 8890, etc.) avoids the problem.

**Old servers accumulate across sessions** (port still bound by zombie python.exe). Always kill by real PID (from netstat), not by bash PID. Use a fresh port if port conflicts persist. See `references/windows-server-management.md`.

### Self-evolve analysis heuristics can be wrong
The `scan_feiyue_project()` function uses filesystem heuristics (checking for module existence, counting evidence files). These can produce false positives:
- **GC detection** was initially a `cleanup-status.json` file probe (always missing) → proposed "GC not configured" even though GC code existed at `feiyue_core/workflow/artifact_gc.py`. **Fix:** check for the module file instead.
- **Review intents** may be from previous bridge cycles, not real actionable feedback — manually inspect before implementing.
- **Always verify proposals** by checking actual API endpoints or source code before implementing.

### Evidence check backfill pattern
When evidence JSON files have `checks=None` and `passing=None`, the Console shows `(?/?)`. The fix is a two-step backend change:

1. **Backfill the evidence JSON** — add `checks`, `passing`, and optionally `checks_detail` to `frontend-dogfood/<run>/evidence.json`
2. **Fix the API** — `_read_frontend_dogfood()` in `runs_api.py` must include `checks` and `passing` in the run dict it returns. Without this, even with correct evidence files, the Console shows `?/?`.
3. **Restart the server** — see "Windows server management" section below

The frontend `renderFrontendDogfood()` already handles both the bridge flat format and the legacy rich format — it reads `run.checks || run.passing`. Fix the API, not the frontend.

### Frontend changes take effect immediately
The Feiyue API server (`create_runs_api_handler`) reads `app.js` and `styles.css` from disk on each HTTP request (via `_send_static_file`). **No server restart needed** after editing `feiyue-web/src/app.js`.

### Bridge evidence format vs existing evidence
Existing Feiyue evidence.json (from G-1..G-10 development) has a rich nested structure with verification results, git status, http probe data, etc. Bridge-generated evidence uses a simple flat format (`title`, `checks`, `passing`, `run_id`, `status`, `task_type`, `hermes_started`, `production_mutated`). The frontend `renderFrontendDogfood()` should handle both — the bridge format needs explicit field access for the new fields.

### Draft ID consistency across a cycle
When a self-evolve analysis creates `draft-id` and writes a draft + intent, the evolve step MUST use the same `--draft-id`. Pass it as returned from the self-evolve analysis step.

## Phase-Driven Self-Evolve (beyond Feiyue artifacts)

For projects needing **iterative multi-phase advancement** (not artifact maintenance):

```
① Analyze actual repo → read code, scan strategies, identify gaps
② Design → architecture doc, stubs, config files
③ Implement → full code, tests, CI workflows
④ Test → run tests, verify checks pass
⑤ Feiyue Record → write draft + evidence + execution + intent per iteration
⑥ Commit → with `feat(phaseN):` prefix
⑦ Repeat on "继续" until phases complete
```

Tips: first iteration = design+stubs; next = core impl; next = gateway+CI.
Each phase gets its own session-draft-id. Use evidence `checks_detail` dict.
Write Feiyue artifacts at each iteration boundary.
See `references/parallel-delegation-pattern.md` for splitting large phases into parallel subagent streams.
See `references/ci-private-submodule-auth.md` for GitHub Actions auth with private submodules — the `sed BEFORE init` pattern proven in VOYAGERAI.

### Weak-model self-evolve (mimo pattern)

Use a **weak/cheap model for analysis**, full model for execution. This is the user's explicit preference:

```
Self-evolve analysis → delegate_task to a cheap/fast model (scan code, find gaps)
Execution            → full model (implement the changes)
Feiyue Record        → full model (write artifacts)
```

**Why:** The self-evolve analysis step (scanning 3 repos for API similarity, comparing 30+ components, identifying duplicates) is data-heavy and pattern-matching — perfect for a cheaper model. The implementation step (patching code, solving type errors, writing tests) needs the full model's reasoning. This 2-tier pattern cuts token cost ~60% on large phases.

**How to do it:** Use `delegate_task` for the analysis step with `toolsets=["terminal"]`. Pass the repo root and explicit scan instructions. The cheap model returns a structured gap table. Then I use the full model to execute each gap fix.

### Don't hardcode repo structure

Each project's submodule layout follows its own narrative logic:

| Project | Structure | Rationale |
|---------|-----------|-----------|
| LexProof | `domains/patent-flow, trademark-flow, ontology` | Separate IP domains that share a knowledge backbone |
| VOYAGERAI | `apps/web, apps/mobile` + `packages/sdk` | App distribution: SDK as shared kernel consumed by both apps |

Phase 1 is always the same (submodules + docs + CI). Phase 2 diverges based on the project type — cross-domain services for LexProof, SDK adoption for VOYAGERAI.

### Submodule modification pattern

When Phase 2+ requires modifying the submodule repos (e.g. SDK adoption, adding Dockerfiles):

```bash
# 1. Work inside the submodule directory
cd apps/web
git checkout main && git pull
# ... make changes (edit files, commit, push) ...
git commit -m "feat: ..." && git push origin main

# 2. Update parent's submodule pointer
cd ..
git add apps/web
git commit -m "chore: update submodule pointer"
git push
```

#### ⚠️ CRITICAL: "不要影响现有仓库" = ZERO modifications

The user's constraint means: do NOT add, modify, or push any file to the submodule repos. Even a single commit is a violation.

**Wrong interpretation:** "don't destroy or restructure the submodules, just add commits to them" ← this is what I did and was corrected.

**Right interpretation:** Keep submodules at their original commits. All integration work (CI/CD, shared components, patch docs, docker-compose, deployment scripts) goes in the PARENT repo's own directories (`integrations/`, `shared/`, `docs/`, `.github/`). Only the user decides when to apply changes to the underlying repos.

**Recovery if you already pushed to submodules:**
1. `git ls-tree <first-parent-commit> <submodule-path>` to get original SHA
2. `git checkout <original-sha>` inside submodule
3. `git push origin HEAD:main --force`
4. `git add <submodule-path>` in parent, commit, push

This was a hard-learned lesson from VOYAGERAI Phase 2.

### Real-World Example: LexProof (3-Phase Consolidation)

**Project:** sinonchum/LexProof — Unified IP Evidence Platform
**Method:** 3 git submodules + shared layer + Phase 3 native services

**Full Feiyue Loop executed 4 times:**

| Cycle | Phase | Subagent Streams | Artifacts Written | Tests Added |
|-------|-------|-----------------|--------------------|-------------|
| 1 | Foundation | 1 (repo exploration) | Standalone docs | — |
| 2 | Phase 2.0-2.2 | 2 (docs + impl) | 4 artifacts | 55 |
| 3 | Phase 2.5-2.6 | 1 (gateway + CI) | 4 artifacts | 46 |
| 4 | Phase 3.1-3.4 | 2 (infra + services) | 4 artifacts | 57 |

**Key patterns used:**
- **Parallel delegation** — used `delegate_task` with multiple items for Phase 3
- **Don't hardcode architecture** — phase-driven, not pre-planned
- **Submodule Dockerfiles** — commit to submodule repos, update parent pointer
- **Feiyue evidence per iteration** — each phase gets its own `.hermes/` set
- **"继续" interface** — user says "继续" to advance one phase

**Pattern template:**
```python
gh repo create --private <org>/<ParentRepo>
git submodule add <url1> domains/module-a
git submodule add <url2> domains/module-b
# Phase 1: Integrate + docs
# Phase 2: Cross-domain services
# Phase 3: Frontend, Docker, CI
```

### Real-World Example: VOYAGERAI (2-Phase Consolidation)

**Project:** sinonchum/VOYAGERAI — AI Travel Concierge, YC W26
**Method:** 3 git submodules (apps/web, apps/mobile, packages/sdk) — apps/packages layout

**Feiyue Loop executed (with mimo pattern):**

| Cycle | Phase | Weak Model Step | Execution | Tests |
|-------|-------|-----------------|-----------|-------|
| 1 | Foundation | (docs, no analysis needed) | Submodules + docs + CI | — |
| 2 | Phase 2 | Gap analysis: 32 components compared | Overlay patches (3 files in integrations/) + CI + compose | 12 SDK tests |
| 3 | Phase 3 | (deploy + Show to Driver) | Root overlay files + deploy workflows + monitoring.ts + APK build | — |
| 4 | Fix | (user correction) | Force-push reverted 3 submodules to original commits | 4 checks |

**Phase 2 highlights:**
- **Self-evolve via delegate_task** used a weak model to scan all 3 repos, identify 32 components, produce a structured comparison table, and rank 3 high-priority gaps
- **Patch overlay pattern**: SDK adoption documented as patch files under `integrations/` — user applies when ready. No submodule repos were modified.
- **Parallel execution** used 2 independent streams: (a) SDK enhancement docs, (b) Web+Mobile adoption docs
- **CI/CD infrastructure** in root: 4 parallel CI jobs, SSH deploy, APK build, docker-compose

**Structure difference from LexProof:** VOYAGERAI used `apps/`+`packages/` because the three repos form a consumption hierarchy (SDK → apps) rather than parallel domains.

## External Project Analysis

Feiyue's artifact structure can be used to document code audits of **third-party projects** that don't use Feiyue themselves. This is useful for:

- Auditing an open-source project for security, quality, and compatibility
- Recording external analysis in a structured, portable format
- Creating a self-contained `.hermes/` archive that can be imported into a Feiyue project later

**Setup pattern:**

```bash
# Clone target repo
git clone --depth 1 <GITHUB_URL> <target-dir>
cd <target-dir>

# Create standard Feiyue artifact structure
mkdir -p .hermes/hermes-session-drafts/{audit-id}
mkdir -p .hermes/frontend-dogfood/{audit-id}
mkdir -p .hermes/execution-output/{audit-id}
mkdir -p .hermes/review-intent-drafts/review-{audit-id}
```

**Standard artifacts to write:**

1. **Session draft** — `draft.json` (title, goal, status, created_by, tool_call_count) + `events.json` (event sequence)
2. **Evidence** — `frontend-dogfood/{audit-id}/evidence.json` (checks, passing, checks_detail dict)
3. **Execution output** — `execution-output/{audit-id}/output.json` (events, hermes_started, dry_run_only)
4. **Review intent** — `review-intent-drafts/review-{audit-id}/intent.json` (title, summary, resolution fields)
5. **Full report** — e.g. `AUDIT_REPORT.md` at project root (markdown with findings organized by severity)

**Limitation:** The Feiyue API server and Console are scoped to a single project root (e.g. `feiyue-review-lf`). Artifacts under an external project's `.hermes/` won't appear in the Console unless the server is restarted with that project root. The artifacts serve as a **portable, self-contained audit record** readable by anyone familiar with the format.

See `references/external-project-audit-ifakelocation.md` for a worked example.

## Important

- Always use the same `--project-root` across bridge calls in a cycle
- Use `--draft-id` from `self-evolve` step when calling `evolve` to close the loop
- The bridge only writes JSON files — no provider calls, no Hermes startup
- Bridge output goes into `.hermes/` under the project root
- See `references/artifact-schemas.md` for the exact JSON format of all 6 artifact types
