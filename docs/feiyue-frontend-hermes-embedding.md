# Feiyue Frontend and Hermes Embedding Architecture

Status: feature-branch proposal  
Branch: `feat/feiyue-frontend-hermes-embed`  
Scope: front-end architecture and safe scaffold for a Feiyue operator console that can embed Hermes-backed agent sessions without exposing credentials or bypassing approval gates.

## Why this exists

Feiyue already has read-only HTML dashboards in `feiyue_core.workflow.runs_api`:

- `/dashboard` — run evidence dashboard.
- `/dashboard/assets` — asset catalog.
- `/dashboard/review-inbox` — pending human review items.
- `/dashboard/runs/<task_id>` — run detail.

Those pages prove a safe inspection surface, but they are server-rendered skeleton pages. The next product step is a real operator console that can:

1. inspect evidence and history;
2. review proposals and approvals;
3. launch or resume Hermes-backed work under explicit controls;
4. show nested Hermes conversations and tool execution evidence;
5. preserve Feiyue's fail-closed boundaries.

## Design principle

The browser is an operator surface, not an agent runtime.

A Feiyue web UI must never directly hold provider keys, Hermes profile secrets, SSH keys, bot tokens, or broad mutation authority. The UI submits reviewable intents to a local Feiyue backend. The backend turns approved intents into Hermes profile/session work and writes evidence back under `.hermes/`.

```text
Browser UI
  -> Feiyue API / BFF
  -> Approval and policy gates
  -> Hermes Bridge sidecar
  -> Hermes profile/session/process
  -> tools/providers/sandboxes
  -> Feiyue evidence store under .hermes/
  -> Browser UI evidence refresh
```

## Proposed packages

```text
packages/feiyue-core/
  feiyue_core/workflow/runs_api.py          # current read-only API/dashboard
  feiyue_core/workflow/hermes_bridge.py     # future typed bridge to Hermes sessions
  feiyue_core/workflow/frontend_api.py      # future JSON/SSE/WebSocket BFF

packages/feiyue-web/
  package.json
  src/index.html
  src/styles.css
  src/app.js
  scripts/validate-static-app.mjs
```

`packages/feiyue-web` starts as a dependency-free static shell. It should be able to run against the existing read-only API first, then grow into a richer app after API contracts are stable.

## UI information architecture

### 1. Overview

Purpose: command-center summary.

Data sources:

- `GET /runs`
- `GET /assets`
- `GET /review-inbox`
- `.hermes/capability-history/latest.json`
- `.hermes/model-routing.yaml` via backend-provided safe summary, not raw filesystem reads from browser.

Shows:

- verified run count;
- pending review count;
- current worker route;
- latest capability tags;
- safety state: provider calls, production mutations, routing mutations.

### 2. Evidence Explorer

Purpose: inspect run evidence and artifacts.

Data sources:

- `GET /runs`
- `GET /runs/<task_id>`
- `GET /runs/<task_id>/handoff`

Rules:

- read-only by default;
- relative paths only;
- raw logs are collapsed and redacted;
- no provider output containing secrets is rendered without backend redaction.

### 3. Review Inbox

Purpose: human review queue.

Data source:

- `GET /review-inbox`

Rules:

- proposal review is visible;
- write actions are disabled until exact approval objects exist;
- every write-side action is represented as an intent, not a direct mutation;
- the backend records approval evidence before applying anything.

### 4. Hermes Agent Console

Purpose: nested Hermes session view inside Feiyue.

This is the important architectural seam. It should not embed Hermes as an uncontrolled browser-side chat widget. Instead, Feiyue owns a Hermes Bridge that creates or attaches to Hermes sessions and streams sanitized events to the frontend.

Capabilities:

- create a session under a named Hermes profile;
- resume a session by id;
- show messages, tool calls, approvals, stdout snippets, and evidence links;
- stream progress with SSE/WebSocket;
- pause/stop a run;
- submit user steering;
- request an approval object.

Non-capabilities in the browser:

- direct provider key access;
- direct shell execution;
- direct mutation of `~/.hermes/config.yaml`;
- bypassing Feiyue policy gates;
- arbitrary profile switching without backend allowlist.

### 5. Capability and Routing

Purpose: inspect weak-worker readiness and routing proposals.

Data sources:

- `.hermes/capability-history/latest.json` via backend summary;
- `.hermes/capability-feedback/latest.json` via backend summary;
- `.hermes/routing-proposals/*/proposal.json` via review inbox or dedicated endpoint;
- `.hermes/model-routing.yaml` via parsed safe summary.

Write-side flow:

```text
User reviews proposal
  -> UI creates approval-intent draft
  -> backend validates proposal hash, routing hash, recommended_changes_hash
  -> backend writes approval evidence
  -> backend applies via RoutingApplyGate
  -> backend writes apply evidence
  -> UI refreshes routing summary
```

## Hermes embedding options

### Option A — iframe external Hermes UI

Feiyue embeds another Hermes UI in an iframe.

Pros:

- fastest if a separate Hermes UI already exists;
- clean process isolation.

Cons:

- hard to bind Feiyue evidence IDs to Hermes sessions;
- difficult to enforce Feiyue-specific approval gates;
- iframe auth/session complexity;
- weak audit trail unless bridged anyway.

Verdict: useful for demos only.

### Option B — browser talks directly to Hermes API

Browser calls Hermes API server directly.

Pros:

- simple mental model.

Cons:

- high secret exposure risk;
- hard to enforce Feiyue policy;
- weak provenance because actions bypass Feiyue's evidence store;
- difficult to support multiple Hermes profiles safely.

Verdict: reject.

### Option C — Feiyue Hermes Bridge sidecar

Browser talks only to Feiyue backend. Feiyue backend talks to Hermes through a typed bridge.

Pros:

- best auditability;
- no browser-side secrets;
- approval gates stay central;
- Hermes sessions can be linked to Feiyue run ids;
- supports streaming nested Hermes events;
- compatible with local profiles, gateway sessions, and later remote workers.

Cons:

- requires new backend contracts;
- needs careful session lifecycle design.

Verdict: recommended.

## Hermes Bridge contract sketch

The bridge should be implemented behind typed Python models before exposing UI writes.

```python
class HermesSessionStartRequest(FeiyueModel):
    run_id: str
    profile: str
    goal: str
    toolsets: list[str]
    workdir: str
    dry_run_only: bool = True
    max_provider_calls: int
    approval_required: bool = True

class HermesSessionEvent(FeiyueModel):
    session_id: str
    run_id: str
    event_type: Literal[
        "message",
        "tool_call",
        "tool_result",
        "approval_requested",
        "evidence_written",
        "completed",
        "blocked",
        "error",
    ]
    redacted_payload: dict[str, Any]
    evidence_path: str | None = None

class HermesSessionControlRequest(FeiyueModel):
    session_id: str
    action: Literal["pause", "resume", "stop", "steer"]
    payload: dict[str, Any] = {}
```

Required invariants:

- `profile` must come from a backend allowlist.
- `workdir` must be project-local or a reviewed workspace path.
- `dry_run_only` defaults true.
- provider call budgets are explicit.
- every tool/action event is redacted before streaming to browser.
- every completed or blocked session writes evidence.

## Backend API phases

### Phase 1 — read-only static web shell

- Keep existing `runs_api.py` endpoints.
- Add `packages/feiyue-web` static shell.
- No write endpoints.
- No Hermes subprocess calls.

### Phase 2 — typed BFF summaries

Add backend-safe summary endpoints:

```text
GET /api/overview
GET /api/runs
GET /api/runs/<task_id>
GET /api/review-inbox
GET /api/assets
GET /api/capabilities
GET /api/routing
```

### Phase 3 — review intent drafting

Add intent endpoints that still do not mutate routing/workflows directly:

```text
POST /api/intents/routing-approval-draft
POST /api/intents/workflow-promotion-approval-draft
POST /api/intents/hermes-session-start-draft
```

These write reviewable drafts only, not final actions.

### Phase 4 — approved local actions

Only after exact approvals exist:

```text
POST /api/apply/routing-proposal
POST /api/run/approved-multi-worker-dry-run
POST /api/hermes/sessions
POST /api/hermes/sessions/<session_id>/control
GET  /api/hermes/sessions/<session_id>/events
```

All write endpoints must call existing Feiyue gates rather than edit files directly.

## State and evidence model

The UI should display state derived from evidence rather than from untracked in-memory objects.

```text
.hermes/runs/...
.hermes/workflow-smokes/...
.hermes/capability-history/...
.hermes/capability-feedback/...
.hermes/routing-proposals/...
.hermes/model-routing.yaml
.hermes/hermes-sessions/<run_id>/session-evidence.json   # future
```

Hermes session evidence should include:

- Hermes profile name;
- Hermes session id;
- Feiyue run id;
- prompt/goal hash;
- toolset allowlist;
- provider call budget;
- redaction status;
- approval ids;
- output evidence paths;
- final status.

## Security boundaries

The frontend must preserve existing Feiyue defaults:

- read-only by default;
- no global Hermes config mutation;
- no provider calls from static docs/tests;
- no production PR, merge, or deploy by default;
- exact approval required before applying routing or promotions;
- browser receives redacted event payloads only;
- no secrets in localStorage;
- no broad approval such as "approve all future runs";
- route/workflow applies must use existing apply gates.

## First implementation slice

This branch should start with:

1. a documented architecture decision;
2. dependency-free `packages/feiyue-web` static shell;
3. dark institutional styling aligned with Feiyue operator use;
4. read-only cards for overview, evidence, review inbox, capability/routing, and Hermes console placeholder;
5. a validation script that proves no enabled write controls are present;
6. tests that pin the scaffold's safety boundaries.

## Open decisions

- Should Feiyue UI be served by `runs_api.py` or by a separate frontend dev server in development?
- Should Hermes Bridge call `hermes chat -q`, an internal Python API, MCP, or a future Hermes API server?
- What is the minimal event schema for nested Hermes streaming that preserves prompt-caching and role alternation constraints?
- How should Telegram/Discord-origin sessions appear in the Feiyue UI without breaking topic/session routing?
- Which profiles are safe to expose in the UI allowlist?
- Should the UI support local-only operator login, OS user auth, or no auth while bound to `127.0.0.1`?

## Dogfood interpretation

The frontend should also become a real Feiyue dogfood workload, not just a UI layer. Each bounded frontend slice can be treated as a Feiyue task:

```text
Feiyue plans a frontend slice
  -> an allowed Hermes-backed worker implements it
  -> Feiyue verifies DOM/API/safety contracts
  -> evidence updates capability history
  -> routing learns whether the worker can handle UI/runtime integration work
  -> the frontend displays the resulting evidence
```

The first dogfood track is documented in [`docs/plans/feiyue-frontend-dogfood-real-task.md`](plans/feiyue-frontend-dogfood-real-task.md).

## Recommendation

Use Option C: Feiyue Backend + Hermes Bridge sidecar.

Build the frontend as an evidence-first console and as Feiyue's own recursive evaluation surface. Let Feiyue remain the policy/evidence layer and let Hermes remain the agent runtime. The browser should never become the place where tools, credentials, or provider decisions live.
