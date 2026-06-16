# Feiyue Lessons from VOYAGERAI Real-Project Consolidation

Date: 2026-06-17  
Project: `sinonchum/VOYAGERAI`  
Source repos: `voyager-ai`, `voyager-ai-mobile`, `voyager-ai-sdk`

## Executive summary

VOYAGERAI proved that Feiyue is most valuable when it is not treated as a local demo framework, but as an execution doctrine for real repositories with CI, private submodules, deployment workflows, and human corrections.

The main upgrade is this rule:

> Feiyue must preserve the production boundary first, then evolve by writing portable evidence, patch overlays, docs, CI, and repeatable scripts in the parent repo.

This differs from earlier Phase-2 behavior where submodule repositories were modified directly. The correction was important: for consolidation projects, the parent repo is the integration surface; original repos remain untouched unless the operator explicitly approves.

## What Feiyue learned

### 1. Real-project self-evolution is phase-driven, not artifact-only

The original self-evolve loop scanned `.hermes/` artifacts and proposed maintenance tasks. VOYAGERAI required a broader loop:

1. Scan the actual repositories and submodules.
2. Compare architecture, APIs, SDK adoption, CI, deployment, and mobile runtime behavior.
3. Produce an implementable phase plan.
4. Execute only in the parent repo unless approval exists for submodule changes.
5. Write Feiyue evidence for the phase.
6. Run GitHub CI and fix real build failures.
7. Commit, push, and repeat.

This is now the recommended pattern for real startup projects.

### 2. Weak-model analysis + strong-model execution works

The VOYAGERAI Phase 2 gap scan used a weak/cheap model to inspect all three repos and identify SDK integration gaps. The strong model then implemented the fixes.

Learned division of labor:

- Weak model: broad scan, component inventory, duplicate detection, API similarity, risk ranking.
- Strong model: code edits, CI fixes, submodule pointer safety, test-driven verification, deployment docs.

This prevents expensive models from spending most of their budget on low-level inventory work.

### 3. Parent repo overlay pattern is the safe default

For a consolidation repo, Feiyue must default to overlays:

- `docs/` for narrative, architecture, roadmap, deployment.
- `integrations/*.patch` for proposed downstream edits.
- `shared/` for reusable parent-owned components.
- `.github/workflows/` for parent-owned CI/CD.
- `.hermes/` for Feiyue evidence and execution history.

Submodules should be treated as read-only source inputs. Even well-intended commits to them violate the operator's “不要影响现有仓库” constraint.

### 4. GitHub CI is part of the evolution loop, not an afterthought

VOYAGERAI exposed a critical CI issue: private submodules cannot be cloned by the default `GITHUB_TOKEN`. The final reliable pattern is:

```yaml
- uses: actions/checkout@v4
  with:
    submodules: false
- name: Init private submodules with PAT
  env:
    PAT: ${{ secrets.VOYAGERAI_PAT }}
  run: |
    sed -i "s|https://github.com/OWNER/PRIVATE|https://x-access-token:${PAT}@github.com/OWNER/PRIVATE|g" .gitmodules
    git submodule init
    git submodule update --init --recursive
```

Critical ordering:

> Rewrite `.gitmodules` before `git submodule init`; after `init`, Git caches the old URL in `.git/config`.

This pattern has been added to the Feiyue bridge skill as a reusable reference.

### 5. CI should distinguish integration regressions from inherited submodule debt

The mobile app had pre-existing dependency and TypeScript issues. Feiyue learned to separate:

- Parent repo integration errors that must fail CI.
- Known inherited submodule errors that should be surfaced but not block the parent consolidation workflow.

Temporary tolerance is acceptable only when documented and scoped, for example `npm ci --legacy-peer-deps` or non-blocking `tsc` for known inherited mobile debt.

### 6. Evidence should be portable across machines

The `.hermes` evidence under VOYAGERAI is useful only if both Hermes instances can read it. Therefore, project-level `.hermes/` artifacts should be committed when they are lightweight, non-secret, and describe a real evolution phase.

Heavy logs, screenshots, raw provider transcripts, and secrets should not be committed.

## Self-evolution upgrades for Feiyue

### New doctrine

Feiyue now has three scopes of learning:

1. **Project evidence** — `.hermes/` inside the project repo records what happened.
2. **Reusable skill** — `hermes-assets/skills/devops/feiyue-bridge/` stores repeatable procedures and pitfalls.
3. **Framework code/docs** — the Feiyue repo stores scripts and doctrine that both Hermes machines can pull.

### New invariant

> If a correction comes from a real project, Feiyue must write it into a portable artifact before the session ends.

For VOYAGERAI, the portable artifacts are:

- `tools/hermes-bridge/feiyue-bridge.py`
- `hermes-assets/skills/devops/feiyue-bridge/`
- this document
- `docs/two-hermes-github-sync.md`

### New pattern: Sync-first evolution

Before starting a major Feiyue-backed project on either Windows or MacBook:

1. Pull the Feiyue repo.
2. Install/sync the Feiyue Hermes skill locally.
3. Run the bridge overview/self-evolve on the target project.
4. Execute the task.
5. Commit project evidence and Feiyue skill updates.
6. Push both the project repo and the Feiyue repo.

This turns GitHub into the shared learning bus between the two Hermes instances.
