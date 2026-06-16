# iFakeLocation (Fauxlocation) — External Project Audit

**Repo:** `master131/iFakeLocation` — https://github.com/master131/iFakeLocation  
**Stars:** ⭐1119  
**Language:** C# .NET 6.0  
**Function:** iOS GPS location simulation via libimobiledevice  
**Audit date:** 2026-06-16

## How the Feiyue artifacts were set up

This was a standalone external audit — not inside the feiyue-review-lf project. The `.hermes/` directory was created inside the cloned repo's root:

```bash
# Clone target repo
git clone --depth 1 https://github.com/master131/iFakeLocation.git fauxlocation-analysis

# Create standard Feiyue artifact structure manually
mkdir -p .hermes/hermes-session-drafts/fauxlocation-audit-001
mkdir -p .hermes/frontend-dogfood/fauxlocation-audit-001
mkdir -p .hermes/execution-output/fauxlocation-audit-001
mkdir -p .hermes/review-intent-drafts/review-fauxlocation-audit-001

# Write 5 standard artifacts
# 1. session draft (draft.json + events.json)
# 2. evidence.json (with checks_detail)
# 3. execution output (output.json)
# 4. review intent (intent.json)
# 5. audit report markdown (project root)
```

**Important:** Because the Feiyue API server is rooted at `feiyue-review-lf`, artifacts under `fauxlocation-analysis/.hermes/` won't appear in the Console. They serve as a portable, self-contained audit record that can be copied into a Feiyue project later.

## Audit findings summary

| Severity | Count | Key findings |
|----------|-------|-------------|
| 🔴 High | 1 | Hardcoded GitHub tree-list hash — upstream breakage risk |
| 🟡 Medium | 3 | `.Result` sync blocking, empty catch swallowing, DvtSimulateLocation stub |
| 🟢 Low | 3 | Path separator hardcode, no CI, no version pinning |
| ✅ Done well | 4 | Cross-platform branching, SafeHandle cleanup, strategy pattern, auto image download |

Full report at `FAUXLOCATION_AUDIT.md` in the cloned repo.
