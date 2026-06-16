# Feiyue Server Management on Windows

## Finding and Killing Stale Servers

The `terminal(background=true)` tool on this Windows/MSYS host wraps commands in `bash.exe`. The PID returned in the tool output is bash, NOT your python server. The actual python.exe is a child process invisible to the tool's PID tracking.

### Detection

```bash
netstat -ano | grep '<PORT>' | grep LISTENING
# → TCP 127.0.0.1:<PORT> 0.0.0.0:0 LISTENING <REAL_PID>
```

If multiple PIDs appear for the same port, they are from different sessions (e.g. `Services` + `Console`).

### Killing

```bash
taskkill //F //PID <REAL_PID>
```

Use the REAL PID from `netstat`, NOT the bash PID from the `background=true` return value.

### Verification

```bash
netstat -ano | grep '<PORT>' | grep LISTENING
# Should return nothing or only your new server
```

## Starting a Fresh Server

```bash
python -u -m feiyue_core.workflow.runs_api \
    --root "C:\Users\serve\AppData\Local\Temp\feiyue-review-lf" \
    --host 127.0.0.1 \
    --port <FREE_PORT>
```

**Port allocation tips:**
- Default port is 8765 (from argparse), but historically 8899 was used for the proxy
- 8897-8899 often have stale bindings from previous sessions
- Use `8897` (or lower) for fresh starts
- The `-u` flag unbuffers stdout so startup messages appear

## Why PIDs Don't Match

Background pattern: `cd /c/path && python ...` → the `cd &&` is a shell construct. MSYS bash creates a `bash.exe` parent that spawns `python.exe` as a child. The tool tracks the `bash.exe` parent. Only `netstat -ano` reveals the actual `python.exe` PID.

## Zombie Accumulation

Every `background=true` call that gets killed via `process(action='kill')` only kills the bash wrapper, not the python child. Over multiple iterations, 5-10 zombie python.exe processes can accumulate, all on the same port. The symptom: curl returns empty (crash from old code) or HTTP 000 (port collision crash before bind).

**Fix:** `taskkill //F //IM python.exe` to nuke all python processes, then restart only your server.

## Editable Install Override

The Hermes venv has an editable install (`_editable_impl_feiyue_core.pth`) pointing to `packages/feiyue-core/`. This means:

```bash
# The .pth file at
C:\Users\serve\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages\_editable_impl_feiyue_core.pth
# Contains:
C:\Users\serve\AppData\Local\Temp\feiyue-review-lf\packages\feiyue-core
```

This redirects `import feiyue_core` to the temp project's source. Edits to files under `packages/feiyue-core/` are live as long as the server process restarts with no stale bytecode.

**Impact:** If you start a server from a *different* working directory, Python still resolves `feiyue_core` through the `.pth` file, not relative to cwd. Always verify which copy is loaded:

```bash
python -c "import feiyue_core; print(feiyue_core.__file__)"
```

If it points outside your project, delete the `.pth` file or use `PYTHONPATH` to override.

## Stale Server Persistence After Code Changes

If you edit Python source files (model definitions, API handlers) but the running server still returns old validation errors even after restart:

1. Kill ALL python processes on the port: `taskkill //F //IM python.exe` (nuclear) or use real PIDs from `netstat`
2. Delete `__pycache__` directories: `find packages/feiyue-core -name __pycache__ -type d -exec rm -rf {} +`
3. Verify on-disk source matches expectations: `grep "model_construct\|real_execution" packages/feiyue-core/feiyue_core/workflow/runs_api.py`
4. Start on a **fresh port** if TIME_WAIT lingers: `netstat -ano | grep <PORT>` shows TIME_WAIT entries for 2+ minutes after shutdown
5. Use `python -u` for unbuffered output so startup errors appear in the process log immediately

Common symptom: editing `ExecutionRequest` model to add a new field → server keeps rejecting it with `extra_forbidden`. The fix is always a stale process or stale bytecode, never a Pydantic bug.**

**Multi-port strategy for rapid iteration:** Keep 3-4 ports (8890, 8891, 8892, 8893) in rotation. When one port gets stuck in TIME_WAIT, switch to the next. After 2-3 minutes the TIME_WAIT clears and the port is reusable. This avoids the 2-minute dead wait per restart cycle.
