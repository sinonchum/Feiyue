# Feiyue Frontend as a Real Dogfood Task

Status: feature-branch execution plan  
Branch: `feat/feiyue-frontend-hermes-embed`  
Purpose: use the Feiyue frontend itself as a real task to test Feiyue's planning, weak-worker execution, verification, capability routing, and Hermes embedding architecture.

## Core idea

The Feiyue frontend should not be treated as a separate product track only. It is also an ideal recursive dogfood workload:

```text
Feiyue plans Feiyue frontend
  -> Hermes-backed worker implements bounded frontend slices
  -> Feiyue verifier checks UI contracts and safety gates
  -> evidence updates capability history
  -> routing proposals learn which workers can do which UI/runtime tasks
  -> Feiyue frontend displays that same evidence
```

This creates a real task loop without requiring production deployment or global Hermes mutation.

## Why frontend is a good Feiyue test workload

A frontend console exercises multiple Feiyue dimensions at once:

- product/spec reasoning: information architecture, operator workflows, review states;
- implementation: HTML/CSS/JS or later React/Vite components;
- safety: disabled write controls, no secrets, no direct provider calls;
- integration: Feiyue read-only APIs, capability history, routing proposals;
- Hermes embedding: session lifecycle, profile allowlists, redacted event streams;
- verification: static tests, DOM contract tests, API contract tests, screenshot review;
- taste selection: visual hierarchy and Simon's restrained dark institutional style.

## Dogfood phases

### G-0 — Current branch scaffold

Already completed in this feature branch:

- new `packages/feiyue-web` dependency-free shell;
- architecture doc for Feiyue backend + Hermes Bridge sidecar;
- disabled Hermes/session/routing controls;
- dark institutional visual baseline;
- frontend architecture tests;
- `npm run validate`, `npm run build`, and targeted pytest pass.

### G-1 — Read-only evidence console

Goal: make the static shell consume real Feiyue read-only summaries.

Implementation scope:

- serve `packages/feiyue-web/dist` or `src` from `runs_api.py` under `/app`;
- add backend-safe summary endpoints:
  - `GET /api/overview`
  - `GET /api/capabilities`
  - `GET /api/routing`
- keep existing endpoints:
  - `GET /runs`
  - `GET /review-inbox`
  - `GET /assets`
- no write endpoints;
- no provider calls;
- no global Hermes config mutation.

Verification:

- API contract tests;
- static validation script;
- browser or HTML smoke verifying the console renders real counts;
- evidence under `.hermes/frontend-dogfood/<run_id>/evidence.json`.

### G-2 — Review intent drafts

Goal: test approval-gated UX without applying anything.

Implementation scope:

- add disabled-to-draft flow for routing proposal review;
- generate reviewable draft intent objects only;
- no direct apply;
- verify draft hashes bind to proposal/routing/capability evidence.

Verification:

- intent draft tests;
- no routing table mutation;
- no provider calls;
- review inbox shows the draft.

### G-3 — Hermes Bridge dry-run session panel

Goal: test nested Hermes session architecture without real provider risk.

Implementation scope:

- introduce typed Hermes Bridge request/event models;
- support fake or provider-free Hermes session events first;
- stream redacted events to frontend via SSE or polling;
- bind events to Feiyue `run_id` and evidence path.

Verification:

- event schema tests;
- redaction tests;
- no browser-side secrets;
- session evidence written under `.hermes/hermes-sessions/<run_id>/`.

### G-4 — Approved local Hermes worker slice

Goal: run a bounded local worker against the frontend codebase.

Implementation scope:

- exact approval required;
- allowlisted profile only, e.g. `local-qwen25-coder` worker lane;
- small frontend task such as "add route card component" or "add read-only capability panel";
- verifier-backed tests before accepting.

Verification:

- provider call budget recorded;
- changed files limited to frontend/API/test scope;
- tests pass;
- evidence updates capability history;
- no production PR/deploy.

## Candidate first real tasks

Good first dogfood tasks:

1. Serve the frontend shell at `/app` from the existing Feiyue API server.
2. Add `/api/overview` summary endpoint.
3. Add `/api/routing` summary endpoint that parses `.hermes/model-routing.yaml` safely.
4. Add `/api/capabilities` summary endpoint from capability-history/latest and feedback/latest.
5. Add a frontend card that displays `worker.primary` and latest capability tags.
6. Add a screenshot/DOM smoke for the dark institutional layout.

Avoid at this stage:

- real provider execution from browser controls;
- direct Hermes API access from frontend;
- changing global Hermes config;
- creating external PRs or deployments;
- enabling broad approval buttons.

## Evidence schema sketch

Each dogfood run should write:

```json
{
  "run_id": "frontend-dogfood-g1-YYYYMMDD",
  "status": "verified",
  "branch": "feat/feiyue-frontend-hermes-embed",
  "task_type": "feiyue_frontend_dogfood",
  "changed_surfaces": ["packages/feiyue-web", "runs_api", "tests"],
  "provider_call_count": 0,
  "global_hermes_config_mutated": false,
  "production_mutated": false,
  "write_controls_enabled": false,
  "verification": {
    "npm_validate": "passed",
    "npm_build": "passed",
    "pytest": "passed"
  }
}
```

## Acceptance gate for each slice

A frontend dogfood slice is accepted only when:

- the task has a bounded scope and explicit changed surfaces;
- safety fields are recorded;
- tests pass;
- evidence is written;
- no browser-side secrets are introduced;
- write-side actions remain disabled unless exact approval evidence exists;
- the UI improves the operator's ability to inspect Feiyue's own evidence.

## Strategic benefit

This turns Feiyue into its own benchmark:

```text
Can Feiyue build, verify, route, and review its own operator console safely?
```

If yes, the frontend becomes more than UI. It becomes a live recursive evaluation surface for Feiyue's core thesis: weak/local workers can become increasingly useful under strong specification, evidence-first verification, sparse teacher help, and human approval gates.
