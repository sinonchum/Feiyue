# Feiyue Operator Guide

This guide is the starting point for safely operating Feiyue evidence, review, and dry-run workflows. It is intentionally documentation-only and does not authorize live provider execution.

## Default posture

- Provider-free first: use fake/profile-free tests and static evidence before any real profile workflow.
- No global Hermes config mutation: do not edit `~/.hermes/config`, profile routing, keys, cron, or provider credentials while following these runbooks.
- Production PR/promotion disabled by default: every workflow starts as `dry_run_only: true` and must show `promotion_attempted: false` until exact approval is recorded.
- Exact authorization: approvals must name the run/proposal id, approved action, changed files, target branch, approver, approval id, reason, and source evidence hash where applicable.
- Review inbox read-only: `review-inbox` lists pending items only; it must not approve, promote, push, or mutate routing.

## Daily operator checks

Run from the repository root unless a command explicitly changes directory.

```bash
cd packages/feiyue-core
python3 -m pytest tests/test_docs_release_contract.py -q
python3 -m feiyue_core.workflow.runs_cli --root ../.. review-inbox --format json
python3 -m feiyue_core.workflow.runs_cli --root ../.. capability-feedback
python3 -m feiyue_core.workflow.runs_cli --root ../.. capability-history
```

Expected safety fields in evidence and reports:

- `dry_run_only: true`
- `promotion_attempted: false`
- `provider_execution_requested: false` for provider-free planning lanes
- `global_hermes_config_mutated: false`
- `routing_table_mutated: false` unless an exact approved routing apply is being audited

## Evidence locations

- Workflow dry-run evidence: `.hermes/workflow-smokes/<run_id>/evidence.json`
- Promotion approval evidence: `.hermes/workflow-approvals/<run_id>/approval.json`
- Promotion result evidence: `.hermes/workflow-promotions/<run_id>/promotion-evidence.json`
- Promotion lifecycle and rollback evidence: `.hermes/promotion-lifecycle/<run_id>/rollback-evidence.json`
- Routing proposals: `.hermes/routing-proposals/<proposal_id>/proposal.json`
- Routing approvals: `.hermes/routing-approvals/<proposal_id>/approval.json`
- Multi-worker plans: `.hermes/multi-worker-plans/<plan_id>/plan.json`

## Operator escalation rules

Stop and request explicit human authorization before:

- Running any real profile/provider smoke.
- Increasing provider/profile call budgets.
- Promoting a dry run to a branch.
- Applying a routing proposal.
- Creating a production PR or pushing to a remote.
- Changing Hermes global or profile configuration.

Use the linked runbooks for exact procedures: [approval runbooks](approval-runbooks.md), [live smoke playbook](live-smoke-playbook.md), [security boundaries](security-boundaries.md), and [rollback guide](rollback-guide.md).
