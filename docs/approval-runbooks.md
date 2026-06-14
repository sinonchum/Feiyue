# Feiyue Approval Runbooks

Approvals are evidence records, not informal chat consent. They must use exact authorization and remain scoped to the named action. Production PR/promotion disabled by default means no promotion command is run until the approval evidence exists and matches the source dry run.

## 1. Review pending items without mutation

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. review-inbox --format json
```

Safety contract: review inbox read-only. The command only lists local pending items; it does not approve, promote, apply routing, call providers, or mutate global Hermes config.

## 2. Approve a verified workflow dry run

Prerequisites:

- `.hermes/workflow-smokes/<run_id>/evidence.json` exists.
- Evidence status is verified.
- Evidence includes `dry_run_only: true` and `promotion_attempted: false`.
- Changed files and target branch are known exactly.
- Human approver confirms this specific action: `promote_verified_dry_run`.

Command:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. approve-promotion <run_id> \
  --target-branch feiyue/operator-reviewed-target \
  --changed-file path/to/file.py \
  --approved-by reviewer-id \
  --approval-id approval-YYYYMMDD-run-id \
  --reason "Approve this verified dry_run_only workflow evidence for the named branch and files only."
```

Do not use secrets in `--reason`. Do not approve broad scopes such as "all files" or "future runs".

## 3. Promote only after approval evidence exists

Promotion is intentionally separate from approval.

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. promote-approved <run_id> \
  --commit-message "docs: promote approved Feiyue dry run"
```

Required post-checks:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. workflow-promotion <run_id>
git status --short
git log --oneline -1
```

The promotion evidence must include rollback evidence references or a rollback ref that can be simulated before any remote PR step.

## 4. Create a fake-first draft PR evidence record

Draft PR mode is intentionally local and fake-first by default: it does not call GitHub, push branches, merge, enable auto-merge, or mutate production. Approval must exactly match the persisted PR plan (`plan_hash`, source branch, target branch, rollback ref, approver, and action `create_draft_pr`).

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. draft-pr-plan <run_id> \
  --allowed-target-branch feiyue/operator-reviewed-target \
  --source-branch candidate/<run_id>
python3 -m feiyue_core.workflow.runs_cli --root ../.. approve-draft-pr <run_id> \
  --approved-by reviewer-id \
  --approval-id approval-YYYYMMDD-draft-pr \
  --reason "Create fake draft PR evidence only; no external PR, merge, or production mutation."
python3 -m feiyue_core.workflow.runs_cli --root ../.. create-approved-draft-pr <run_id>
```

Expected evidence: `external_pr_created: false`, `draft: true`, `auto_merge: false`, `mutates_production: false`, `approval_applies: true`, and rollback ref preserved. Any mismatch fails closed with reason codes and still records no external PR creation.

## 5. Approve and apply a routing proposal

Prerequisites:

- Proposal was generated from capability feedback.
- Proposal says `requires_human_approval`.
- No automatic routing mutation has occurred; confirm `routing_table_mutated: false` before approval.

Commands:

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. routing-proposal \
  --proposal-id proposal-YYYYMMDD-routing-review \
  --write-proposal
python3 -m feiyue_core.workflow.runs_cli --root ../.. approve-routing-proposal \
  --proposal-id proposal-YYYYMMDD-routing-review \
  --approved-by reviewer-id \
  --approval-id approval-YYYYMMDD-routing-review \
  --reason "Apply this reviewed routing proposal only."
python3 -m feiyue_core.workflow.runs_cli --root ../.. apply-approved-routing \
  --proposal-id proposal-YYYYMMDD-routing-review
```

## 6. Approve a multi-worker dry run

This approval permits a bounded dry run only. It does not permit production promotion.

```bash
cd packages/feiyue-core
python3 -m feiyue_core.workflow.runs_cli --root ../.. approve-multi-worker-dry-run \
  --plan-id plan-YYYYMMDD-low-risk \
  --approved-by reviewer-id \
  --approval-id approval-YYYYMMDD-multi-worker \
  --reason "Run the named multi-worker plan as dry_run_only only." \
  --max-profile-calls 1
python3 -m feiyue_core.workflow.runs_cli --root ../.. run-approved-multi-worker-dry-run \
  --plan-id plan-YYYYMMDD-low-risk \
  --run-id run-YYYYMMDD-low-risk \
  --source-repo /absolute/path/to/repo \
  --project-name feiyue-safe-dry-run \
  --task-id task-YYYYMMDD \
  --title "Low-risk dry-run task" \
  --scope "Dry-run only; no promotion." \
  --file-to-modify path/to/file.py \
  --verification-command "python3 -m pytest tests/test_docs_release_contract.py -q" \
  --acceptance-criterion "Evidence records dry_run_only: true" \
  --profile-runner fake
```

Expected fields: `dry_run_only: true`, `promotion_attempted: false`, and `global_hermes_config_mutated: false`.
