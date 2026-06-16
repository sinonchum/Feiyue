# External Project Audit Example: FauxLocation (MasqueGPS)

**Type:** Private repo audit variant  
**Repo:** `sinonchum/FauxLocation` (private, discovered via `gh auth status` + `gh repo clone`)  
**Public face:** `sinonchum/MasqueGPS` (docs/screenshots only)

## Discovery Pattern

The user said "my fauxlocation repo." Public GitHub Search API returned 0 results. The public repo list showed `MasqueGPS` (docs-only) but not the source code. The actual repo is **private** — found via `gh` CLI:

```bash
gh auth status           # confirms logged in as sinonchum
gh repo clone sinonchum/FauxLocation  # clones private repo directly
```

## Project Overview

Android mock-location app with **4-layer architecture**:

| Layer | Tech | Purpose |
|-------|------|---------|
| 1. UI/Service | Kotlin + Jetpack Compose | WebView map, foreground service, Shizuku+su provider |
| 2. GNSS HAL | Java Reflection (`GnssHalInjector.kt`) | AIDL proxy to `android.hardware.gnss.IGnss` |
| 3. Ptrace Injector | C NDK (`injector.c`) | Attaches to system_server, calls `dlopen` |
| 4. ART Hook | C NDK (`native_hook.cpp`) | Hooks `isFromMockProvider()` + `GnssLocationProvider.reportLocation()` |

## Key Findings (Feiyue Audit)

### 🔴 Critical (affects build / security)

1. **NDK toolchain hardcoded to `darwin-x86_64`** — `app/build.gradle.kts:124` breaks Linux/Windows builds
2. **`gradle.properties` has hardcoded JVM path** — `/Users/fqn/...` prevents CI/other devs building
3. **`runShizukuCommands()` doesn't use Shizuku** — method body is `Runtime.getRuntime().exec(arrayOf("sh", "-c", ...))`, not actual Shizuku IPC
4. **APK signing password hardcoded** — `tools/apk_patcher.py:33`: `"fauxlocation"`
5. **BootReceiver auto-starts with no safety check** — 10s after boot, starts mocking saved coords

### 🟡 Medium

6. **`MainActivity.kt` 1718 lines** — UI, i18n, root commands, all in one file
7. **`gnss_inject.cpp` uses `system("service call gnss ...")`** — fragile across Android versions
8. **`hal_inject.c` is skeleton only** — binder protocol not implemented
9. **i18n in giant `when` blocks** — hardcoded in source, not maintainable
10. **`apk_patcher.py` paths bound to macOS** — `~/Library/Android/sdk`, Homebrew hardcoded

### 🟢 Low

11. `AppSecurity.getExpectedSignatureHash()` returns empty string — needs production hash
12. `abiFilters` only `arm64-v8a` — no x86_64 emulator support
13. `injector.c.bak` residual file

### Architecture Strengths

- Each layer works independently (Provider → HAL → Injector → Hook)
- `native_hook.cpp` correctly hooks `isFromMockProvider()` + `isMock()` at ART level (strongest anti-detection)
- Signature verification + emulator detection double security
- Shizuku + su dual-mode fallback
- 6-language i18n

## Feiyue Artifacts Created

Standard 5-artifact structure under `FauxLocation-analysis/.hermes/`:

```
.hermes/
├── hermes-session-drafts/fauxlocation-audit-001/draft.json
├── hermes-session-drafts/fauxlocation-audit-001/events.json
├── frontend-dogfood/fauxlocation-audit-001/evidence.json
├── execution-output/fauxlocation-audit-001/output.json
└── review-intent-drafts/review-fauxlocation-audit-001/intent.json
```

## When to Use This Pattern

- User references a repo that doesn't appear in public GitHub search → try `gh repo clone`
- 4-layer or multi-language project → worth documenting each layer's audit separately
- Commercial/proprietary codebase → keep audit artifacts private alongside the repo
