from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from feiyue_core.workflow.promotion_lifecycle import (
    DraftPRApproval,
    DraftPRStatus,
    approve_draft_pr,
    compute_pr_plan_hash,
    GitHubDraftPRAdapter,
    create_approved_draft_pr,
    create_promotion_pr_plan,
)
from tests.test_promotion_lifecycle import _git, _init_toy_repo, _promote_with_production_request


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    package_root = Path(__file__).resolve().parents[1]
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(package_root) if not existing else f"{package_root}{os.pathsep}{existing}"
    return env


def test_create_approved_draft_pr_uses_fake_adapter_and_never_mutates_production(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = _promote_with_production_request(repo, run_id="run-draft-pr", target_branch="production/main")
    plan = create_promotion_pr_plan(
        project_root=repo,
        run_id=run_id,
        allowed_target_branches=["production/main"],
        source_branch="candidate/run-draft-pr",
    )
    approval = approve_draft_pr(
        project_root=repo,
        run_id=run_id,
        approved_by="human-reviewer",
        approval_id="approval-draft-pr",
        reason="Open a draft PR for human review only.",
    )

    evidence = create_approved_draft_pr(project_root=repo, run_id=run_id, approval=approval)

    assert evidence.status == DraftPRStatus.CREATED
    assert evidence.adapter == "fake"
    assert evidence.external_pr_created is False
    assert evidence.draft is True
    assert evidence.auto_merge is False
    assert evidence.mutates_production is False
    assert evidence.rollback_ref == plan.rollback_ref
    assert evidence.approval_applies is True
    assert evidence.reason_codes == ["draft_pr_approval_applies", "fake_adapter_no_external_pr_created"]
    assert evidence.source_branch == "candidate/run-draft-pr"
    assert evidence.target_branch == "production/main"
    assert evidence.plan_hash == compute_pr_plan_hash(plan)
    persisted = json.loads((repo / ".hermes" / "promotion-lifecycle" / run_id / "draft-pr-evidence.json").read_text(encoding="utf-8"))
    assert persisted["external_pr_created"] is False
    assert persisted["mutates_production"] is False


def test_github_draft_pr_adapter_creates_draft_pr_without_automerge_or_production_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = _promote_with_production_request(repo, run_id="run-github-draft", target_branch="production/main")
    plan = create_promotion_pr_plan(
        project_root=repo,
        run_id=run_id,
        allowed_target_branches=["production/main"],
        source_branch="candidate/run-github-draft",
    )
    approval = approve_draft_pr(
        project_root=repo,
        run_id=run_id,
        approved_by="human-reviewer",
        approval_id="approval-github-draft-pr",
        reason="Open a GitHub draft PR for human review only.",
    )
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **kwargs):
        calls.append(command)
        assert kwargs["cwd"] == repo
        if command[:3] == ["gh", "pr", "create"]:
            assert "--draft" in command
            assert "--base" in command and "production/main" in command
            assert "--head" in command and "candidate/run-github-draft" in command
            assert "--title" in command
            assert "--json" not in command
            return subprocess.CompletedProcess(command, 0, stdout="https://github.com/example/repo/pull/42\n", stderr="")
        assert command[:3] == ["gh", "pr", "view"]
        assert "https://github.com/example/repo/pull/42" in command
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "number": 42,
                    "url": "https://github.com/example/repo/pull/42",
                    "isDraft": True,
                    "state": "OPEN",
                    "headRefName": "candidate/run-github-draft",
                    "baseRefName": "production/main",
                }
            ),
            stderr="",
        )

    evidence = create_approved_draft_pr(
        project_root=repo,
        run_id=run_id,
        approval=approval,
        adapter=GitHubDraftPRAdapter(project_root=repo, subprocess_runner=fake_runner),
    )

    assert evidence.status == DraftPRStatus.CREATED
    assert evidence.adapter == "github"
    assert evidence.external_pr_created is True
    assert evidence.draft is True
    assert evidence.auto_merge is False
    assert evidence.mutates_production is False
    assert evidence.pr_number == 42
    assert evidence.pr_url == "https://github.com/example/repo/pull/42"
    assert evidence.reason_codes == ["draft_pr_approval_applies", "github_draft_pr_created"]
    assert calls and calls[0][:3] == ["gh", "pr", "create"]


def test_draft_pr_creation_fails_closed_for_missing_approval(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = _promote_with_production_request(repo, run_id="run-no-approval", target_branch="production/main")
    create_promotion_pr_plan(
        project_root=repo,
        run_id=run_id,
        allowed_target_branches=["production/main"],
        source_branch="candidate/run-no-approval",
    )

    evidence = create_approved_draft_pr(project_root=repo, run_id=run_id, approval=None)

    assert evidence.status == DraftPRStatus.BLOCKED
    assert evidence.approval_applies is False
    assert "missing_draft_pr_approval" in evidence.reason_codes
    assert evidence.external_pr_created is False
    assert evidence.mutates_production is False


def test_draft_pr_creation_fails_closed_for_exact_approval_mismatch(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = _promote_with_production_request(repo, run_id="run-mismatch", target_branch="production/main")
    create_promotion_pr_plan(
        project_root=repo,
        run_id=run_id,
        allowed_target_branches=["production/main"],
        source_branch="candidate/run-mismatch",
    )
    bad_approval = DraftPRApproval(
        approval_id="approval-bad",
        approved_by="human-reviewer",
        run_id=run_id,
        approved_action="create_draft_pr",
        plan_hash="not-the-plan-hash",
        source_branch="candidate/run-mismatch",
        target_branch="production/main",
        rollback_ref=_git(repo, "rev-parse", "HEAD"),
        approved_at="2026-06-14T12:00:00Z",
        reason="Bad hash should fail closed.",
    )

    evidence = create_approved_draft_pr(project_root=repo, run_id=run_id, approval=bad_approval)

    assert evidence.status == DraftPRStatus.BLOCKED
    assert evidence.approval_applies is False
    assert "approval_plan_hash_mismatch" in evidence.reason_codes
    assert evidence.external_pr_created is False
    assert evidence.mutates_production is False


def test_draft_pr_cli_plan_approve_and_create_fake_first(tmp_path: Path) -> None:
    repo = tmp_path / "toy-repo"
    _init_toy_repo(repo)
    run_id = _promote_with_production_request(repo, run_id="run-cli-draft", target_branch="production/main")

    plan = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "draft-pr-plan",
            run_id,
            "--allowed-target-branch",
            "production/main",
            "--source-branch",
            "candidate/run-cli-draft",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    plan_payload = json.loads(plan.stdout)
    assert plan_payload["external_pr_created"] is False
    assert plan_payload["draft"] is True
    assert plan_payload["auto_merge"] is False
    assert plan_payload["mutates_production"] is False

    approve = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "approve-draft-pr",
            run_id,
            "--approved-by",
            "human-reviewer",
            "--approval-id",
            "approval-cli-draft",
            "--reason",
            "Create fake draft PR evidence only.",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    approval_payload = json.loads(approve.stdout)
    assert approval_payload["approved_action"] == "create_draft_pr"
    assert approval_payload["plan_hash"] == plan_payload["plan_hash"]

    create = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(repo),
            "create-approved-draft-pr",
            run_id,
        ],
        text=True,
        capture_output=True,
        check=True,
        env=_cli_env(),
    )
    evidence = json.loads(create.stdout)
    assert evidence["status"] == "created"
    assert evidence["adapter"] == "fake"
    assert evidence["external_pr_created"] is False
    assert evidence["draft"] is True
    assert evidence["auto_merge"] is False
    assert evidence["mutates_production"] is False
    assert evidence["approval_applies"] is True
