# Parallel Delegation Pattern for Large Phases

## When to Use
When a phase has 2+ independent workstreams, use `delegate_task` with parallel tasks to halve wall-clock time.

## LexProof Phase 3 Example

**Stream A (Infra):** Dockerfiles + CI + Compose (66s)
**Stream B (Services):** Copilot + Graph + Reports (342s)

```python
# Both launched simultaneously:
delegate_task(goal="Stream A: Docker + CI", context="...")  # 66s
delegate_task(goal="Stream B: Copilot + Graph + Reports", context="...")  # 342s
# Total wall time: ~342s (B bound) instead of ~408s serial
```

## Key Rules
1. Streams must be **truly independent** — no shared file writes that could conflict
2. Each stream gets its own `context` with all background info (no cross-stream communication)
3. The parent is responsible for **merging outputs** (updating shared files that both touched)
4. Both streams return at the same time — the parent waits for the slower one
5. Streams can themselves use `delegate_task` (nested, but be careful about max depth)

## Common Split Patterns

| Phase Content | Split A | Split B |
|---------------|---------|---------|
| Infrastructure + Services | Dockerfiles, CI | Service code, tests |
| Frontend + Backend | UI pages | API endpoints |
| Docs + Implementation | Documentation | Code + tests |
| Config + Logic | YAML/JSON configs | Python implementation |

## Pitfalls
- **Shared file edits** — both streams may modify the same file (e.g. both add imports). Parent must reconcile.
- **Submodule operations** — committing to submodules inside a delegate task is unreliable (different git contexts). Prefer parent-level commits.
- **Context length** — very large context increases subagent startup time. Keep context focused.
