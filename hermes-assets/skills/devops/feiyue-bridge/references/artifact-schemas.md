# Feiyue Artifact JSON Schemas

Reference for all 6 artifact types the bridge writes and the Feiyue Console reads.
Each lives under `.hermes/<category>/<draft-id>/`.

---

## 1. Hermes Session Draft

**File:** `.hermes/hermes-session-drafts/<id>/draft.json`

```json
{
  "draft_id": "session-001",
  "status": "executed",
  "goal_hash": "a1b2c3",
  "profile": "default",
  "created_by": "hermes-agent",
  "reason": "hermes_session_completed",
  "toolsets": ["file", "terminal"],
  "dry_run_only": false,
  "provider_call_budget": 0,
  "provider_call_count": 0,
  "tool_call_count": 15,
  "hermes_started": true,
  "global_hermes_config_mutated": false,
  "status": "executed",
  "approval_required": false,
  "resolution": "Stale blocked draft from g3 phase",
  "resolved_by": "hermes-self-evolve-cycle-3",
  "resolved_at": "2026-06-16T17:52:00Z",
  "next_required_gate": "none_self_evolved",
  "created_at": "2026-06-16T15:40:17.143383Z",
  "events_path": ".hermes/hermes-session-drafts/lv1-bridge-integration/events.json"
}
```

**Events file:** `.hermes/hermes-session-drafts/<id>/events.json`

```json
[
  {
    "sequence": 1,
    "event_type": "session_draft_created",
    "message": "Draft created for: Feiyue Bridge Lv1",
    "redacted": false,
    "provider_call_count": 0,
    "tool_call_count": 0,
    "created_at": "2026-06-16T15:40:17.143383Z"
  }
]
```

---

## 2. Approval Gate

**File:** `.hermes/approval-gate/<draft-id>/approval.json`

```json
{
  "approval_id": "draft-001",
  "draft_id": "draft-001",
  "approved_by": "simon",
  "reason": "Rate-limiter scoped to /api/inference",
  "status": "approved_dry_run",
  "draft_status_before_approval": "blocked",
  "draft_status_after_approval": "approved",
  "dry_run_only_verified": true,
  "provider_call_budget_verified": 0,
  "no_hermes_start_verified": true,
  "no_production_mutation_verified": true,
  "approved_at": "2026-06-15T10:05:00+00:00",
  "events_path": ".hermes/approval-gate/draft-001/events.json",
  "verifier_evidence_path": ".hermes/approval-gate/draft-001/verifier-evidence.json"
}
```

**Events:** `.hermes/approval-gate/<id>/events.json` — same format as session events
**Verifier evidence:** `.hermes/approval-gate/<id>/verifier-evidence.json`

```json
{
  "approval_id": "draft-001",
  "draft_id": "draft-001",
  "boundary_preserved": true,
  "provider_call_count_after_approval": 0,
  "hermes_started_after_approval": false,
  "verification_checks": {"dry_run": true, "budget": true},
  "approved_at": "2026-06-15T10:05:01+00:00"
}
```

---

## 3. Execution Output

**File:** `.hermes/execution-output/<draft-id>/output.json`

**Dry-run (replay approval events):**
```json
{
  "session_draft_id": "draft-001",
  "executed_by": "feiyue-operator-console",
  "executed_at": "2026-06-15T10:06:00+00:00",
  "events": [
    {
      "sequence": 1,
      "event_type": "dry_run_approved",
      "message": "Replayed: dry-run rate-limiter",
      "redacted": true,
      "provider_call_count": 0,
      "tool_call_count": 0,
      "created_at": "2026-06-15T10:06:00+00:00",
      "execution_phase": "replay"
    }
  ],
  "event_count": 1,
  "provider_call_count": 0,
  "tool_call_count": 0,
  "hermes_started": false,
  "dry_run_only": true
}
```

**Real Hermes CLI:**
```json
{
  "session_draft_id": "draft-001",
  "executed_by": "feiyue-operator-console",
  "executed_at": "2026-06-15T10:06:00+00:00",
  "events": [
    {
      "sequence": 1,
      "event_type": "hermes_cli_started",
      "execution_phase": "hermes_cli",
      "message": "Hermes CLI started for draft draft-001",
      "redacted": false,
      "provider_call_count": 0,
      "tool_call_count": 0,
      "created_at": "2026-06-15T10:06:00+00:00"
    },
    {
      "sequence": 2,
      "event_type": "hermes_cli_completed",
      "execution_phase": "hermes_cli",
      "message": "Hermes CLI finished with exit code 0",
      "exit_code": 0,
      "stdout_preview": "...real Hermes response...",
      "stderr_preview": "",
      "redacted": false,
      "provider_call_count": 0,
      "tool_call_count": 0,
      "created_at": "2026-06-15T10:06:00+00:00"
    }
  ],
  "event_count": 2,
  "provider_call_count": 0,
  "tool_call_count": 0,
  "hermes_started": true,
  "dry_run_only": false
}
```

---

## 4. Frontend Dogfood (Evidence)

**File:** `.hermes/frontend-dogfood/<evidence-id>/evidence.json`

**Bridge format (simple):**
```json
{
  "title": "G-12 GC Logic",
  "checks": 3,
  "passing": 3,
  "provider_call_count": 0,
  "run_id": "feat-gc-logic",
  "status": "completed",
  "task_type": "g-12_gc_logic",
  "global_hermes_config_mutated": false,
  "production_mutated": true,
  "hermes_started": true
}
```

**Legacy format (from G-1..G-10 development, richer):**
```json
{
  "run_id": "g1-readonly-console",
  "status": "verified",
  "task_type": "feiyue_frontend_g1_readonly_console",
  "provider_call_count": 0,
  "branch": "feat/feiyue-frontend-g1-readonly-console",
  "frontend_routes_added": ["/app"],
  "api_routes_added": ["/api/overview"],
  "git_status_after_verification": [" M packages/..."],
  "verification": {
    "http_probe": {"/api/overview": {"status": 200, "bytes": 521}},
    "pytest_output": ""
  }
}
```

**Frontend reads via** `_read_frontend_dogfood()` in `runs_api.py`:
- Extracts: `run_id`, `status`, `task_type`, `provider_call_count`, `global_hermes_config_mutated`, `production_mutated`
- Bridge's `checks`/`passing`/`hermes_started` are NOT extracted by the API — they need to be read from the raw JSON when displayed in the frontend

---

## 5. Review Intent Draft

**File:** `.hermes/review-intent-drafts/<intent-id>/intent.json`

```json
{
  "intent_id": "review-session-001",
  "intent_kind": "routing_review_draft",
  "item_type": "self_evolve",
  "item_id": "session-001",
  "recommended_action": "config_change",
  "evidence_path": ".hermes/frontend-dogfood/session-001/evidence.json",
  "created_by": "feiyue-bridge",
  "reason": "self_evolve:GC not configured",
  "status": "drafted",
  "resolution": "Bridge script running successfully",
  "resolved_by": "hermes-self-evolve-cycle-3",
  "resolved_at": "2026-06-16T17:52:00Z",
  "next_required_gate": "human_review_then_exact_approval",
  "draft_only": false,
  "mutates_state": true,
  "provider_call_count": 0,
  "global_hermes_config_mutated": false,
  "production_mutated": true,
  "writes_approval": false,
  "applies_routing": false,
  "starts_hermes_session": false,
  "created_at": "2026-06-16T15:43:22.562395Z"
}
```

---

## 6. GC Status (read-only, from API)

**Endpoint:** `GET /api/cleanup/status?ttl_days=7`

```json
{
  "total_artifacts": 22,
  "expired_artifacts": 0,
  "active_artifacts": 22,
  "total_size_bytes": 46053,
  "expired_size_bytes": 0,
  "ttl_days": 7,
  "categories": {
    "session drafts": 4,
    "execution outputs": 3,
    "review intent drafts": 4,
    "frontend dogfood runs": 11
  },
  "mutates_state": false,
  "provider_call_count": 0,
  "hermes_started": false
}
```

---

## Server Endpoints (for reference)

| Endpoint | Method | Purpose |
|---|---|---|
| `/app` | GET | Main operator console (SPA) |
| `/api/overview` | GET | Dashboard summary (all artifact types) |
| `/api/hermes-session-drafts` | GET | List all session drafts |
| `/api/approval-gate` | GET | List all approvals |
| `/api/execution-output` | GET | List execution outputs |
| `/api/frontend-dogfood` | GET | List evidence runs (what frontend displays) |
| `/api/review-intents` | GET | List review intent drafts |
| `/api/audit-trail` | GET | Aggregated audit trail across sources |
| `/api/cleanup/status` | GET | GC status |
| `/api/session-timeline/<id>` | GET | Livecycle timeline for a specific draft |
| `/api/hermes-session-drafts` | POST | Create a new session draft |
| `/api/hermes-session-drafts/<id>/approve-dry-run` | POST | Approve a draft |
| `/api/hermes-session-drafts/<id>/execute-approved` | POST | Execute approved draft (`real_execution: true` → real Hermes CLI; default → dry-run replay) |
| `/api/cleanup/run` | POST | Run artifact GC cleanup |
