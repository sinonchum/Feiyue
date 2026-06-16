# SDK Adoption Gap Analysis — Multi-Repo Pattern

## When to Use
When consolidating a monorepo where one submodule is a shared SDK/library and the others are consuming apps. The goal is to eliminate duplicate type definitions, normalization logic, and API client implementations by having all apps import from the SDK.

## The Pattern (mimo-style)

### Step 1 — Analyze (weak model via delegate_task)
```python
delegate_task(
    goal="Analyze SDK adoption gap between SDK and consuming apps",
    context=f"""
        Structure:
        - packages/sdk/ — @project/sdk (shared kernel)
        - apps/web/ — consuming app
        - apps/mobile/ — consuming app

        Read packages/sdk/src/index.ts for ALL exports.
        Search each consuming app for local duplicates of each export.
        Return structured comparison table.
    """,
    toolsets=["terminal"]
)
```

Returns a table like:
| Component | SDK has? | Web has? | Mobile has? | Gap | Action |
|-----------|---------|----------|-------------|-----|--------|
| Trip type | ✅ | yes (own) | no | web duplicates | Replace web with SDK import |

### Step 2 — Execute (3 parallel streams)

1. **SDK enhancement** — Add missing fields apps need (all optional!)
   - `Place`: lat, lng, summary, type
   - `ChatMessage`: shared message type
   - Script detection utilities
   
2. **Web adoption** — Replace local types with SDK imports
   - Use intersection types for app-specific fields:
     `type WebDay = Day & { date: string; country: string }`
   - Remove local type definitions
   - Replace utility functions with SDK re-exports

3. **Mobile adoption** — Create adapter pattern for RN compatibility
   - `src/adapters/sdk-adapter.ts` re-exports SDK types + functions
   - Replace local normalization with SDK's functions
   - Replace local cleanup utilities with SDK's

### Step 3 — Update parent pointers
```bash
git add apps/web apps/mobile packages/sdk
git commit -m "chore: update submodule pointers for SDK adoption"
git push
```

## Pitfalls
- **Optional fields** — All new SDK fields MUST be optional (`?`) to avoid breaking existing code that doesn't use them
- **Intersection types** — Apps can extend SDK types locally without modifying SDK:
  ```typescript
  import { Place } from '@voyager-ai/sdk'
  type WebPlace = Place & { country: string; city: string; intendedDays: number }
  ```
- **RN compatibility** — React Native may not resolve Node.js-style packages. Create an adapter file that re-exports what RN can handle.
- **Zero tsc errors** must be the target — partial adoption breaks CI immediately
- **Commit to submodule repos first**, then update parent pointers — never the reverse
