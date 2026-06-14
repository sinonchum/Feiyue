# Feiyue Release Checklist

This checklist defines the current provider-free release gate for Feiyue. It is intentionally conservative: releases can ship provider-free foundations, examples, reports, and CI contracts, but must not imply that real provider execution, Hermes profile routing, or production promotion automation is enabled.

## Scope

Current release scope:

- Provider-free runtime, workflow, safety, evidence, API/dashboard/export, example smoke, and benchmark smoke foundations.
- CI-verifiable docs and commands.
- No real provider credentials.
- No Hermes configuration mutation.
- Future real-provider work must follow `docs/real-provider-integration-plan.md` before any real provider execution, Hermes profile subprocess, real HTTP smoke, teacher escalation, or real weak-model vs strong-model benchmark.

Out of scope without explicit authorization:

- Real provider execution requires explicit authorization.
- Hermes config mutation is out of scope.
- Real Hermes profile scheduling is out of scope.
- Real project promotion / rollback automation is out of scope; release-candidate and production-promotion readiness gates are fake-first, local-only evidence checks with `production_mutated: false`.
- Real weak-model vs strong-model benchmark calls are out of scope.

## Required Local Gates

Run from `packages/feiyue-core` unless noted otherwise.

1. Compile package:

   ```bash
   python -m compileall -q feiyue_core
   ```

2. Full test suite:

   ```bash
   python -m pytest -q
   ```

   Current baseline: 685 passed

3. Static export-all smoke:

   ```bash
   TMP=$(mktemp -d)
   mkdir -p "$TMP/project/.hermes/runs/ci-smoke"
   python -m feiyue_core.workflow.runs_export_all --root "$TMP/project" --out "$TMP/report" --bundle "$TMP/report.zip"
   ```

   Expected marker: `STATIC_EXPORT_ALL_OK`

4. Provider-free example smoke:

   ```bash
   TMP=$(mktemp -d)
   python -m feiyue_core.examples.provider_free_smoke \
     --root "$TMP/example-project" \
     --out "$TMP/example-report" \
     --bundle "$TMP/example-report.zip"
   ```

   Expected marker: `PROVIDER_FREE_EXAMPLE_SMOKE_OK`

5. Provider-free benchmark smoke:

   ```bash
   TMP=$(mktemp -d)
   python -m feiyue_core.evaluation.benchmark_runner \
     --quick \
     --output "$TMP/benchmark.json" \
     --output-markdown "$TMP/benchmark.md"
   ```

   Expected marker: `BENCHMARK_SMOKE_OK`

6. Secret scan from repository root:

   ```bash
   ! git grep -I -n -E '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----)' -- . ':!*.pyc' ':!.git' && echo SECRET_SCAN_OK
   ```

   Expected marker: `SECRET_SCAN_OK`

7. Git state:

   ```bash
   git diff --check
   git status --short
   ```

   Expected result: no whitespace errors and a clean tree after commit.

## Release Candidate / Production Promotion Safety Gate

Before any production-promotion claim, create and verify a local release candidate bundle. This gate is fake-first and fail-closed: it writes evidence under `.hermes/release-candidates/<release_id>/`, performs no push/API/merge/deploy action, and every successful readiness record must keep `production_mutated: false`.

Required evidence:

- Verified draft PR evidence (`.hermes/promotion-lifecycle/<run_id>/draft-pr-evidence.json`) or promoted branch evidence (`.hermes/workflow-promotions/<run_id>/promotion-evidence.json`).
- Successful CI evidence (`status`, `conclusion`, or `result` of `success`, or boolean success/pass).
- Target branch in the explicit `--allowed-target-branch` allowlist.
- Verified rollback simulation/evidence (`rollback-evidence.json` with `status: verified` and no external side effect).
- Non-empty post-promotion verification plan.
- Exact production-promotion approval hash generated from the persisted release-candidate plan.

Provider-free CLI flow:

```bash
python -m feiyue_core.workflow.runs_cli --root "$PROJECT" release-candidate-plan wave5-6 \
  --run-id "$RUN_ID" \
  --allowed-target-branch production/main \
  --ci-evidence-path .hermes/ci/success.json \
  --rollback-evidence-path .hermes/promotion-lifecycle/$RUN_ID/rollback-evidence.json \
  --post-promotion-verification-command "python -m pytest -q"

python -m feiyue_core.workflow.runs_cli --root "$PROJECT" approve-production-promotion wave5-6 \
  --approved-by "$REVIEWER" \
  --approval-id "$APPROVAL_ID" \
  --reason "Approve exact dry-run readiness only."

python -m feiyue_core.workflow.runs_cli --root "$PROJECT" verify-production-promotion-readiness wave5-6
```

Expected readiness marker: `status: ready`, `dry_run: true`, and `production_mutated: false`. Missing CI evidence, missing rollback evidence, a non-allowlisted branch, or an approval hash mismatch must produce `status: blocked`.

## Required Remote Gate

After pushing to `main`, GitHub Actions must complete successfully for the pushed commit. Do not report release readiness from local tests alone.

Required CI gates:

- compileall
- pytest
- static export-all smoke
- provider-free example smoke
- provider-free benchmark smoke
- secret scan

## Release Notes Requirements

Release notes must include:

- Commit SHA.
- Full test baseline.
- GitHub Actions run URL.
- Provider-free scope statement.
- Explicit list of gated/unimplemented real-provider work.
- Confirmation that no credentials, tokens, API keys, passwords, or connection strings were added.

## Authorization Boundaries

Do not proceed without explicit human approval for:

- Adding or reading real provider credentials.
- Modifying Hermes model/provider/profile configuration.
- Running real LLM calls.
- Enabling real multi-worker routing.
- Promoting changes into external production repositories.
- Storing long-lived sensitive artifacts.
