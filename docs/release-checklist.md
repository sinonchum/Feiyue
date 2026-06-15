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

   Current baseline: 703 passed

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

## Wave13-1 deploy/rollback readiness

The latest evidence-only deployment boundary is `wave13-1-deploy-rollback-readiness-20260615`.

- Scope: readiness design only.
- Source readiness evidence: `.hermes/merge-readiness/wave8-8e-pr3-nondraft-merge-readiness-refresh/evidence.json`.
- Verification command: `feiyue-runs verify-merge-rollback-deploy-readiness wave13-1-deploy-rollback-readiness-20260615`.
- Expected marker: `approval_applies: true`.
- Required safety booleans: `merge_performed: false`, `auto_merge_enabled: false`, `deploy_performed: false`, and `production_mutated: false`.
- Real deploy remains blocked until a concrete target environment, rollback command, post-deploy health check, and exact deployment approval are supplied.

## Wave14-1 through Wave14-4 closure batch

`Wave14ClosureRunner` executed `wave14-closure-20260615` as the latest no-deploy closure evidence.

- Wave14-1: `longitudinal_task_count: 3` and `longitudinal_teacher_call_rate_delta: -1.0`.
- Wave14-2: `operator_cockpit_v1_ready: true` and `evidence_explorer_verified: true`.
- Wave14-3: `routing_learning_apply_loop_ready: true`, `routing_table_mutated: false`, and human-reviewed apply remains required before mutation.
- Wave14-4: `deploy_target_selected: local-release-artifact`, `requires_exact_deploy_approval: true`, `deploy_performed: false`, and `production_mutated: false`.
- Treat this as release-artifact readiness, not a production deployment.

## Wave14 real-environment 1-4 authorized run

Executed `wave14-real-env-1to4-20260615` after explicit user authorization (`我授权，真实环境跑一轮1-4`).

- Wave14-1: one real `feiyue-mid-deepseek-pro` Hermes profile subprocess call completed with `status: verified`, `provider_call_count: 1`, source repo clean, dry-run-only execution, no promotion, and no global Hermes config mutation.
- Wave14-2: exported `.hermes/static-run-reports/wave14-real-env-1to4-20260615-operator-cockpit.zip`; `static_export_all_ok: true`; review inbox remained read-only.
- Wave14-3: generated `wave14-real-env-1to4-20260615-routing-learning-proposal`; **safe routing apply hold** remains because the proposal includes stale/non-installed `steady-4c` alongside the real `feiyue-mid-deepseek-pro` recommendation. Do not apply until the stale profile recommendation is filtered or explicitly approved; current `routing_table_mutated: false`.
- Wave14-4: verified `wave14-real-env-1to4-20260615-local-release-artifact-readiness-v2`; local release artifact readiness is ready, but `deploy_performed: false` and `production_mutated: false` because no external production target was supplied.

## Wave14 filtered Routing Apply

Executed after user instruction to run Routing Apply before deployment discussion.

- Proposal: `wave14-real-env-1to4-20260615-routing-learning-filtered`.
- Filter: `steady-4c excluded` because it is a stale/non-installed historical recommendation.
- Result: `status: applied`; `applied_profiles: feiyue-mid-deepseek-pro`; `routing_table_mutated: false` because the route already pointed at `feiyue-mid-deepseek-pro`.
- Deployment remains untouched: `deploy_performed: false`, `production_mutated: false`.

## Wave14 Deployment 1 GitHub Release Artifact

Published after explicit approval (`同意Deployment 1`).

- Release: `wave14-real-env-20260615` — https://github.com/sinonchum/Feiyue/releases/tag/wave14-real-env-20260615
- Asset: `wave14-real-env-1to4-20260615-operator-cockpit.zip`
- Asset SHA256: `b6913a8cf30c4e1f2bfcacfcc421717744edf0a972ef596f3f849c3e4bf8301e`
- Source commit: `c09f8ab8e7cd3f1b0b2c0b4b98880eaf3aba5aed`
- CI: https://github.com/sinonchum/Feiyue/actions/runs/27543390141
- Verification: `post_download_manifest_verify: STATIC_REPORT_VERIFY_OK checked_files=3`
- Deployment scope: `deploy_target: github_release_artifact`; `deploy_performed: true`; no service started; no external API deployed; `production_mutated: false`.

## Wave14 Deployment 2 GitHub Pages Static Cockpit

Published after the user selected option A: a standalone public Pages repo containing only the exported static cockpit.

- Public repo: `sinonchum/Feiyue-operator-cockpit` — https://github.com/sinonchum/Feiyue-operator-cockpit
- Cockpit URL: https://sinonchum.github.io/Feiyue-operator-cockpit/wave14-real-env-20260615/
- public_pages_commit: 964c138914c567d1b0f0102597df1bd23e3a28d4
- Source asset: `wave14-real-env-1to4-20260615-operator-cockpit.zip`
- Source asset SHA256: `b6913a8cf30c4e1f2bfcacfcc421717744edf0a972ef596f3f849c3e4bf8301e`
- Verification: `index.html`, `manifest.json`, `assets/index.html`, and `review-inbox/index.html` returned HTTP 200; remote manifest matched local.
- Deployment scope: `deploy_target: github_pages_static_cockpit_public_repo`; `deploy_performed: true`; `github_pages_config_mutated: true`; `private_source_repo_publicized: false`; `external_api_deployed: false`; `provider_call_count: 0`; `production_mutated: false`.
