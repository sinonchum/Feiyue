# Provider-Free Smoke Example

This example is a copy-pasteable M14 smoke path for Feiyue's provider-free foundation. It creates a tiny generated calculator git repo, runs the existing fake student/fake teacher workflow, persists run evidence, renders a fallback handoff summary, exports a static run report, verifies the manifest, builds a portable ZIP bundle, extracts it, and verifies the extracted bundle.

It does **not** call real LLM providers and does **not** mutate Hermes configuration.

## Run

From `packages/feiyue-core`:

```bash
python -m feiyue_core.examples.provider_free_smoke \
  --root /tmp/feiyue-provider-free-example \
  --out /tmp/feiyue-provider-free-example-report \
  --bundle /tmp/feiyue-provider-free-example-report.zip
```

Expected exit code: `0`

Expected success marker:

```text
PROVIDER_FREE_EXAMPLE_SMOKE_OK
```

The `--root` directory must be empty or absent because the smoke initializes a fresh toy git repository.

## Outputs

- `<root>/.hermes/runs/m14-provider-free-example-smoke/run-evidence.json`
- `<root>/.hermes/runs/m14-provider-free-example-smoke/handoff-summary.md`
- `<out>/index.html`
- `<out>/manifest.json`
- `<out>/runs/m14-provider-free-example-smoke.html`
- `<bundle>`
- `<bundle>.extracted/manifest.json`

## What this proves

- Provider-free execution can recover from an initial verifier failure using deterministic teacher guidance.
- Run evidence is persisted for fallback handoff.
- The read-only static report pipeline is exportable, hash-verifiable, bundleable, extractable, and verifiable again.
