# Real Provider Integration Plan

This document is a plan only. It defines the authorization, safety, evidence, and rollback boundaries required before Feiyue may move from provider-free fake integrations to any real provider execution. It does not implement real provider calls, does not require credentials, and does not authorize anyone to read, print, copy, or store real secrets.

## Scope and Required Boundaries

Real-provider work is gated future work. Before any execution, a human owner must explicitly authorize the exact provider, profile, command, network scope, budget, and evidence-retention rules.

The gated surfaces are:

- real provider execution: any request to an external model/provider endpoint or paid provider service.
- Hermes profile subprocess: any subprocess invocation that routes through a real Hermes profile, model, or provider configuration.
- real HTTP smoke: any networked smoke test, even a minimal health check or single prompt.
- teacher escalation: any fallback from a weak/student role to a real strong/teacher model or provider-backed repair path.
- real weak/strong benchmark: any benchmark that compares live weak and strong providers or incurs real model calls.

Each gated surface requires explicit human authorization before use. Authorization for one surface does not authorize any other surface.

## Required Sequence

The first real-provider lane must follow this sequence in order:

1. provider-free fake tests
   - Keep all existing fake provider/profile tests passing.
   - Add or update contract tests using fake runners before any real-provider smoke is considered.
   - Confirm provider-free example and benchmark smokes still pass without network or credentials.
2. redaction/diagnostics
   - Verify diagnostics classify timeouts, authentication/configuration failures, subprocess failures, and unknown failures without leaking sensitive values.
   - Confirm logs, exceptions, run evidence, markdown reports, and handoff summaries redact tokens, API keys, passwords, and connection strings.
3. explicit authorization
   - Obtain a written approval record from the human owner naming the allowed provider, Hermes profile, command, budget, timeout, network scope, and artifact-retention policy.
   - Record that approval with the run evidence before executing any real HTTP smoke, Hermes profile subprocess, teacher escalation, or real weak/strong benchmark.
4. isolated dry-run/smoke
   - Run only the approved isolated dry-run/smoke command.
   - Use a temporary project/profile sandbox and the smallest possible request.
   - Do not expand from dry-run to teacher escalation or benchmarks without separate approval.
5. no global Hermes config mutation
   - Do not mutate global Hermes config, default profiles, shared credentials, shell startup files, or long-lived model routing state.
   - Prefer temporary environment/process scope and disposable directories.
6. auditable run evidence
   - Persist command, timestamp, commit SHA, approving human, scope, expected cost class, exit code, redacted stdout/stderr, diagnostic classification, and produced artifacts.
   - Make evidence sufficient for a reviewer to verify what ran without exposing credentials.
7. rollback/abort gates
   - Stop immediately on unexpected network target, unexpected cost, missing authorization, failed redaction, unclassified diagnostic, config mutation attempt, or evidence-writing failure.
   - Preserve redacted failure evidence and document whether any cleanup was needed.

## Authorization Checklist

A real-provider run may start only when every item below is checked by a human owner:

- [ ] The approving human is named in the run record.
- [ ] The exact provider and model/profile are named.
- [ ] The command and working directory are specified.
- [ ] The run type is specified: real HTTP smoke, Hermes profile subprocess, teacher escalation, or real weak/strong benchmark.
- [ ] The maximum request count, timeout, and budget/cost ceiling are specified.
- [ ] The expected network destination or provider endpoint class is specified.
- [ ] The credential source is provided by the human/operator outside the repository and is not committed, printed, copied, or requested by the test suite.
- [ ] The evidence-retention location and redaction expectations are specified.
- [ ] Rollback/abort gates are acknowledged.
- [ ] The owner confirms that no global Hermes config mutation is allowed unless a separate authorization explicitly says otherwise.

## Forbidden Actions

These actions are forbidden for this documentation lane and remain forbidden for future implementation lanes unless a human authorization explicitly supersedes them:

- Do not implement real provider calls in this documentation lane.
- Do not read, print, copy, or commit real credentials.
- Do not add realistic fake secrets, placeholder tokens that resemble real tokens, or provider keys to tests/docs.
- Do not mutate global Hermes configuration, default profile routing, shell startup files, or shared credential stores.
- Do not run real HTTP smoke, Hermes profile subprocess, teacher escalation, or real weak/strong benchmark without explicit human authorization.
- Do not use network access as part of provider-free tests.
- Do not persist raw provider responses when they may contain secrets or private data.
- Do not promote real-provider results into production or external repositories without a separate approval gate.

## Evidence Template

A future authorized run should record, at minimum:

```text
commit_sha: <git commit under test>
approved_by: <human owner>
authorized_scope: <single approved surface>
provider_or_profile: <approved provider/profile name only>
command: <exact command>
started_at: <timestamp>
ended_at: <timestamp>
exit_code: <integer>
diagnostic_kind: <redacted classification>
stdout_redacted: <path or summary>
stderr_redacted: <path or summary>
artifacts: <redacted artifact paths>
abort_gate_triggered: <none or reason>
```

The template is intentionally textual and secret-free. It is not a credential file and must not be expanded with secret values.
