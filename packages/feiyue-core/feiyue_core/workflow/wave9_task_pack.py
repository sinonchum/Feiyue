from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from feiyue_core.providers.profile_runner import ProfileRunRequest
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.profile_worker_bridge import ProfileRunnerLike, _parse_candidate_writes

Wave9AssignmentRole = Literal["implementation", "tests", "docs", "review", "verifier"]
Wave9MergeStrategy = Literal["reject_on_conflict", "ordered_overlay", "reviewer_selected_patch"]


class Wave9AuthorizationCheckStatus(StrEnum):
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"


class Wave9ExecutionStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    BLOCKED = "blocked"


class Wave9LocalPRPlanStatus(StrEnum):
    PLANNED = "planned"
    BLOCKED = "blocked"


class Wave9LocalBranchMaterializationStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    BLOCKED = "blocked"


class Wave9LocalBranchCommitStatus(StrEnum):
    COMMITTED = "committed"
    FAILED = "failed"
    BLOCKED = "blocked"


class Wave9DraftPRStatus(StrEnum):
    CREATED = "created"
    FAILED = "failed"
    BLOCKED = "blocked"


class Wave9PRSemanticReviewStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"


class Wave9CapabilityIngestionStatus(StrEnum):
    INGESTED = "ingested"
    BLOCKED = "blocked"


class Wave9TaskAssignment(FeiyueModel):
    assignment_id: str
    profile_id: str
    role: Wave9AssignmentRole
    objective: str
    allowed_files: list[str]
    verifier_commands: list[str]
    max_profile_calls: int = Field(default=1, ge=1)
    depends_on_assignment_ids: list[str] = Field(default_factory=list)

    @field_validator("assignment_id", "profile_id", "role", "objective")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("assignment fields must be non-empty")
        return normalized

    @field_validator("allowed_files", "verifier_commands")
    @classmethod
    def _required_string_list(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("allowed_files and verifier_commands must contain non-empty strings")
        return normalized


class Wave9TaskPack(FeiyueModel):
    task_pack_id: str
    task_id: str
    title: str
    summary: str
    assignments: list[Wave9TaskAssignment]
    merge_strategy: Wave9MergeStrategy = "reject_on_conflict"
    verifier_commands: list[str]
    review_criteria: list[str]
    dry_run_only: bool = True
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    provider_call_count: int = 0
    reason_codes: list[str]
    task_pack_hash: str | None = None

    @field_validator("task_pack_id", "task_id", "title", "summary")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("task pack fields must be non-empty")
        return normalized

    @field_validator("verifier_commands", "review_criteria", "reason_codes")
    @classmethod
    def _required_list(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("task pack lists must contain non-empty strings")
        return normalized

    @field_validator("assignments")
    @classmethod
    def _at_least_two_assignments(cls, value: list[Wave9TaskAssignment]) -> list[Wave9TaskAssignment]:
        if len(value) < 2:
            raise ValueError("Wave9 task packs require at least two assignments")
        assignment_ids = [assignment.assignment_id for assignment in value]
        if len(set(assignment_ids)) != len(assignment_ids):
            raise ValueError("assignment_id values must be unique")
        return value

    @model_validator(mode="after")
    def _safe_pre_execution_contract(self) -> "Wave9TaskPack":
        if self.dry_run_only is not True:
            raise ValueError("Wave9 task packs must be dry_run_only")
        if self.promotion_attempted is not False:
            raise ValueError("Wave9 task packs cannot attempt promotion")
        if self.global_hermes_config_mutated is not False:
            raise ValueError("Wave9 task packs cannot mutate global Hermes config")
        if self.production_mutated is not False:
            raise ValueError("Wave9 task packs cannot mutate production")
        if self.provider_call_count != 0:
            raise ValueError("Wave9 task packs are pre-execution and must have provider_call_count 0")
        seen: set[str] = set()
        overlaps: set[str] = set()
        for assignment in self.assignments:
            for file_path in assignment.allowed_files:
                if file_path in seen:
                    overlaps.add(file_path)
                seen.add(file_path)
        if overlaps and self.merge_strategy != "reject_on_conflict":
            raise ValueError("overlapping assignment scopes require reject_on_conflict")
        return self


class Wave9TaskPackAuthorization(FeiyueModel):
    approval_id: str
    approved_by: str
    task_pack_id: str
    task_id: str
    approved_action: str
    task_pack_hash: str
    worker_profile_ids: list[str]
    verifier_commands: list[str]
    merge_strategy: Wave9MergeStrategy
    dry_run_only: bool = True
    max_total_profile_calls: int = Field(ge=0)
    provider_call_count: int = 0
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator("approval_id", "approved_by", "task_pack_id", "task_id", "approved_action", "task_pack_hash", "reason")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("authorization fields must be non-empty")
        return normalized

    @field_validator("worker_profile_ids", "verifier_commands")
    @classmethod
    def _required_list(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("authorization lists must contain non-empty strings")
        return normalized

    @model_validator(mode="after")
    def _safe_authorization_contract(self) -> "Wave9TaskPackAuthorization":
        if self.approved_action != "execute_wave9_real_multi_worker_dry_run":
            raise ValueError("approved_action must be execute_wave9_real_multi_worker_dry_run")
        if self.dry_run_only is not True:
            raise ValueError("Wave9 authorization must be dry_run_only")
        if self.provider_call_count != 0:
            raise ValueError("Wave9 authorization is pre-execution and must have provider_call_count 0")
        if self.promotion_attempted is not False:
            raise ValueError("Wave9 authorization cannot attempt promotion")
        if self.global_hermes_config_mutated is not False:
            raise ValueError("Wave9 authorization cannot mutate global Hermes config")
        if self.production_mutated is not False:
            raise ValueError("Wave9 authorization cannot mutate production")
        return self


class Wave9AuthorizationCheck(FeiyueModel):
    task_pack_id: str
    status: Wave9AuthorizationCheckStatus
    authorization_applies: bool = False
    approval_id: str | None = None
    approved_action: str | None = None
    task_pack_hash: str
    worker_profile_ids: list[str]
    verifier_commands: list[str]
    merge_strategy: Wave9MergeStrategy
    dry_run_only: bool = True
    max_total_profile_calls: int = 0
    provider_call_count: int = 0
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    reason_codes: list[str]


class Wave9AssignmentExecutionReport(FeiyueModel):
    assignment_id: str
    profile_id: str
    role: str
    status: str
    candidate_files: list[str] = Field(default_factory=list)
    allowed_scope: bool = True
    exit_code: int = 0
    reason_codes: list[str] = Field(default_factory=list)


class Wave9ExecutionReport(FeiyueModel):
    run_id: str
    task_pack_id: str
    task_id: str
    status: Wave9ExecutionStatus
    authorization_applies: bool = False
    approval_id: str | None = None
    assignment_reports: list[Wave9AssignmentExecutionReport] = Field(default_factory=list)
    provider_call_count: int = Field(default=0, ge=0)
    reason_codes: list[str]
    conflict_files: list[str] = Field(default_factory=list)
    verifier_outputs: list[dict[str, object]] = Field(default_factory=list)
    sandbox_path: str | None = None
    dry_run_only: bool = True
    promotion_attempted: bool = False
    external_pr_created: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    source_repo_clean: bool = True


class Wave9LocalPRPlan(FeiyueModel):
    plan_id: str
    execution_run_id: str
    task_pack_id: str
    task_id: str
    status: Wave9LocalPRPlanStatus
    target_branch: str
    title: str
    changed_files: list[str] = Field(default_factory=list)
    verifier_commands: list[str] = Field(default_factory=list)
    review_checklist: list[str] = Field(default_factory=list)
    provider_call_count: int = 0
    reason_codes: list[str]
    dry_run_only: bool = True
    promotion_attempted: bool = False
    external_pr_created: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    source_repo_clean: bool = True

    @field_validator("plan_id", "execution_run_id", "task_pack_id", "task_id", "target_branch", "title")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Wave9 local PR plan fields must be non-empty")
        return normalized

    @model_validator(mode="after")
    def _local_only_contract(self) -> "Wave9LocalPRPlan":
        if self.provider_call_count != 0:
            raise ValueError("Wave9 local PR plans are provider-free")
        if self.dry_run_only is not True:
            raise ValueError("Wave9 local PR plans must remain dry_run_only")
        if self.promotion_attempted or self.external_pr_created or self.merge_performed or self.deploy_performed:
            raise ValueError("Wave9 local PR plans cannot promote, create PRs, merge, or deploy")
        if self.global_hermes_config_mutated or self.production_mutated:
            raise ValueError("Wave9 local PR plans cannot mutate global config or production")
        return self


class Wave9LocalBranchMaterializationApproval(FeiyueModel):
    approval_id: str
    approved_by: str
    approved_action: str
    plan_id: str
    execution_run_id: str
    plan_hash: str
    target_branch: str
    changed_files: list[str]
    verifier_commands: list[str]
    local_only: bool = True
    provider_call_count: int = 0
    external_pr_created: bool = False
    branch_pushed: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @model_validator(mode="after")
    def _safe_contract(self) -> "Wave9LocalBranchMaterializationApproval":
        if self.approved_action != "materialize_wave9_local_pr_plan":
            raise ValueError("approved_action must be materialize_wave9_local_pr_plan")
        if self.local_only is not True or self.provider_call_count != 0:
            raise ValueError("Wave9 materialization approval must be local-only and provider-free")
        if self.external_pr_created or self.branch_pushed or self.merge_performed or self.deploy_performed or self.production_mutated:
            raise ValueError("Wave9 materialization approval cannot authorize external PRs, push, merge, deploy, or production mutation")
        return self


class Wave9LocalBranchMaterialization(FeiyueModel):
    materialization_id: str
    plan_id: str
    execution_run_id: str
    status: Wave9LocalBranchMaterializationStatus
    approval_id: str | None = None
    local_branch_name: str
    worktree_path: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    verifier_outputs: list[dict[str, object]] = Field(default_factory=list)
    provider_call_count: int = 0
    reason_codes: list[str]
    local_branch_created: bool = False
    branch_pushed: bool = False
    external_pr_created: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False
    source_repo_clean: bool = True

    @model_validator(mode="after")
    def _local_only_contract(self) -> "Wave9LocalBranchMaterialization":
        if self.provider_call_count != 0:
            raise ValueError("Wave9 materialization is provider-free")
        if self.branch_pushed or self.external_pr_created or self.merge_performed or self.deploy_performed:
            raise ValueError("Wave9 materialization cannot push, create PRs, merge, or deploy")
        if self.promotion_attempted or self.global_hermes_config_mutated or self.production_mutated:
            raise ValueError("Wave9 materialization cannot promote, mutate config, or mutate production")
        return self


class Wave9LocalBranchCommitApproval(FeiyueModel):
    approval_id: str
    approved_by: str
    approved_action: str
    materialization_id: str
    materialization_hash: str
    plan_id: str
    execution_run_id: str
    local_branch_name: str
    changed_files: list[str]
    verifier_commands: list[str]
    local_only: bool = True
    provider_call_count: int = 0
    branch_pushed: bool = False
    external_pr_created: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @model_validator(mode="after")
    def _safe_contract(self) -> "Wave9LocalBranchCommitApproval":
        if self.approved_action != "commit_wave9_local_branch":
            raise ValueError("approved_action must be commit_wave9_local_branch")
        if self.local_only is not True or self.provider_call_count != 0:
            raise ValueError("Wave9 commit approval must be local-only and provider-free")
        if self.branch_pushed or self.external_pr_created or self.merge_performed or self.deploy_performed or self.production_mutated:
            raise ValueError("Wave9 commit approval cannot authorize push, PR, merge, deploy, or production mutation")
        return self


class Wave9LocalBranchCommit(FeiyueModel):
    commit_id: str
    materialization_id: str
    plan_id: str
    execution_run_id: str
    status: Wave9LocalBranchCommitStatus
    approval_id: str | None = None
    local_branch_name: str
    worktree_path: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    local_commit_created: bool = False
    local_commit_sha: str | None = None
    verifier_outputs: list[dict[str, object]] = Field(default_factory=list)
    provider_call_count: int = 0
    reason_codes: list[str]
    branch_pushed: bool = False
    external_pr_created: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False

    @model_validator(mode="after")
    def _local_only_contract(self) -> "Wave9LocalBranchCommit":
        if self.provider_call_count != 0:
            raise ValueError("Wave9 local branch commits are provider-free")
        if self.branch_pushed or self.external_pr_created or self.merge_performed or self.deploy_performed:
            raise ValueError("Wave9 local branch commits cannot push, create PRs, merge, or deploy")
        if self.promotion_attempted or self.global_hermes_config_mutated or self.production_mutated:
            raise ValueError("Wave9 local branch commits cannot promote, mutate config, or mutate production")
        return self



class Wave9DraftPRApproval(FeiyueModel):
    approval_id: str
    approved_by: str
    approved_action: str
    commit_id: str
    local_commit_sha: str
    local_branch_name: str
    changed_files: list[str]
    commit_hash: str
    target_branch: str
    draft_only: bool = True
    provider_call_count: int = 0
    branch_push_authorized: bool = True
    external_pr_creation_authorized: bool = True
    auto_merge_enabled: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @model_validator(mode="after")
    def _safe_contract(self) -> "Wave9DraftPRApproval":
        if self.approved_action != "create_wave9_draft_pr":
            raise ValueError("approved_action must be create_wave9_draft_pr")
        if self.draft_only is not True:
            raise ValueError("Wave9 PR approval must be draft-only")
        if self.provider_call_count != 0:
            raise ValueError("Wave9 PR approval must be provider-free")
        if not self.branch_push_authorized or not self.external_pr_creation_authorized:
            raise ValueError("Wave9 Draft PR approval must explicitly authorize branch push and PR creation")
        if self.auto_merge_enabled or self.merge_performed or self.deploy_performed or self.production_mutated:
            raise ValueError("Wave9 Draft PR approval cannot authorize auto-merge, merge, deploy, or production mutation")
        return self


class Wave9DraftPR(FeiyueModel):
    pr_id: str
    commit_id: str
    materialization_id: str
    plan_id: str
    execution_run_id: str
    status: Wave9DraftPRStatus
    approval_applies: bool = False
    approval_id: str | None = None
    local_branch_name: str
    target_branch: str
    changed_files: list[str] = Field(default_factory=list)
    local_commit_sha: str | None = None
    branch_pushed: bool = False
    external_pr_created: bool = False
    draft: bool = True
    state: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    head_ref: str | None = None
    base_ref: str | None = None
    adapter: str = "fake"
    provider_call_count: int = 0
    reason_codes: list[str]
    auto_merge_enabled: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    production_mutated: bool = False

    @model_validator(mode="after")
    def _draft_pr_contract(self) -> "Wave9DraftPR":
        if self.provider_call_count != 0:
            raise ValueError("Wave9 Draft PR evidence is provider-free")
        if self.draft is not True:
            raise ValueError("Wave9 external PR must be draft")
        if self.auto_merge_enabled or self.merge_performed or self.deploy_performed:
            raise ValueError("Wave9 Draft PR cannot enable auto-merge, merge, or deploy")
        if self.promotion_attempted or self.global_hermes_config_mutated or self.production_mutated:
            raise ValueError("Wave9 Draft PR cannot promote, mutate config, or mutate production")
        return self


class Wave9DraftPRAdapter:
    name = "fake"

    def create_draft_pr(self, *, source_branch: str, target_branch: str, title: str, body: str) -> dict[str, object]:
        return {
            "branch_pushed": False,
            "external_pr_created": False,
            "draft": True,
            "state": "FAKE",
            "auto_merge": False,
            "pr_number": None,
            "pr_url": f"fake://wave9-draft-pr/{source_branch}",
            "head_ref": source_branch,
            "base_ref": target_branch,
        }


class Wave9GitHubDraftPRAdapter(Wave9DraftPRAdapter):
    name = "github"

    def __init__(self, *, project_root: str | Path, worktree_path: str | Path, subprocess_runner=subprocess.run) -> None:
        self.project_root = Path(project_root)
        self.worktree_path = Path(worktree_path)
        self._subprocess_runner = subprocess_runner

    def create_draft_pr(self, *, source_branch: str, target_branch: str, title: str, body: str) -> dict[str, object]:
        push = self._subprocess_runner(["git", "push", "-u", "origin", source_branch], cwd=self.worktree_path, text=True, capture_output=True, check=False)
        if push.returncode != 0:
            raise RuntimeError(push.stderr.strip() or push.stdout.strip() or "git push failed")
        create = self._subprocess_runner(
            ["gh", "pr", "create", "--draft", "--base", target_branch, "--head", source_branch, "--title", title, "--body", body],
            cwd=self.project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if create.returncode != 0:
            # If a PR already exists, gh usually says so; resolve it by listing/viewing the head branch.
            list_pr = self._subprocess_runner(
                ["gh", "pr", "list", "--head", source_branch, "--state", "open", "--json", "number,url,isDraft,state,headRefName,baseRefName,autoMergeRequest", "--limit", "1"],
                cwd=self.project_root,
                text=True,
                capture_output=True,
                check=False,
            )
            if list_pr.returncode != 0:
                raise RuntimeError(create.stderr.strip() or create.stdout.strip() or "gh pr create failed")
            existing = json.loads(list_pr.stdout or "[]")
            if not existing:
                raise RuntimeError(create.stderr.strip() or create.stdout.strip() or "gh pr create failed")
            payload = existing[0]
        else:
            pr_url = _extract_wave9_pr_url(create.stdout)
            if not pr_url:
                raise RuntimeError("gh pr create did not return a PR URL")
            view = self._subprocess_runner(
                ["gh", "pr", "view", pr_url, "--json", "number,url,isDraft,state,headRefName,baseRefName,autoMergeRequest"],
                cwd=self.project_root,
                text=True,
                capture_output=True,
                check=False,
            )
            if view.returncode != 0:
                raise RuntimeError(view.stderr.strip() or view.stdout.strip() or "gh pr view failed")
            payload = json.loads(view.stdout or "{}")
        if payload.get("isDraft") is not True:
            raise RuntimeError("Wave9 GitHub PR is not draft")
        if payload.get("headRefName") != source_branch or payload.get("baseRefName") != target_branch:
            raise RuntimeError("Wave9 GitHub PR branch mismatch")
        if payload.get("autoMergeRequest") is not None:
            raise RuntimeError("Wave9 GitHub PR unexpectedly has auto-merge enabled")
        return {
            "branch_pushed": True,
            "external_pr_created": True,
            "draft": True,
            "state": payload.get("state"),
            "auto_merge": False,
            "pr_number": payload.get("number") if isinstance(payload.get("number"), int) else None,
            "pr_url": payload.get("url") if isinstance(payload.get("url"), str) else None,
            "head_ref": payload.get("headRefName"),
            "base_ref": payload.get("baseRefName"),
        }



class Wave9PRSemanticReview(FeiyueModel):
    review_id: str
    pr_id: str
    status: Wave9PRSemanticReviewStatus
    required_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    missing_required_terms: list[str] = Field(default_factory=list)
    present_forbidden_terms: list[str] = Field(default_factory=list)
    provider_call_count: int = 0
    mutates_state: bool = False
    external_pr_mutated: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    reason_codes: list[str]


class Wave9CapabilityIngestion(FeiyueModel):
    ingestion_id: str
    status: Wave9CapabilityIngestionStatus
    execution_run_id: str
    commit_id: str
    pr_id: str
    semantic_review_id: str
    capability_record_written: bool = False
    evaluation_record_written: bool = False
    provider_call_count: int = 0
    routing_table_mutated: bool = False
    merge_performed: bool = False
    deploy_performed: bool = False
    production_mutated: bool = False
    reason_codes: list[str]


class Wave9TaskPackExecutor:
    def __init__(self, *, profile_runner: ProfileRunnerLike) -> None:
        self._profile_runner = profile_runner

    def run(
        self,
        *,
        project_root: str | Path,
        source_repo: str | Path,
        project_name: str,
        task_pack: Wave9TaskPack,
        authorization: Wave9TaskPackAuthorization | None,
        run_id: str,
    ) -> Wave9ExecutionReport:
        root = Path(project_root)
        source = Path(source_repo)
        check = validate_wave9_task_pack_authorization(pack=task_pack, authorization=authorization)
        if check.status is Wave9AuthorizationCheckStatus.BLOCKED:
            report = _wave9_report(
                run_id=run_id,
                task_pack=task_pack,
                status=Wave9ExecutionStatus.BLOCKED,
                authorization_applies=False,
                approval_id=authorization.approval_id if authorization else None,
                provider_call_count=0,
                reason_codes=check.reason_codes,
                source_repo_clean=_source_clean(source),
            )
            write_wave9_execution_evidence(report, root)
            return report

        sandbox = wave9_execution_sandbox_path(root, run_id)
        if sandbox.exists():
            shutil.rmtree(sandbox)
        shutil.copytree(source, sandbox, ignore=shutil.ignore_patterns(".git", ".hermes", "__pycache__", ".pytest_cache"))

        provider_call_count = 0
        assignment_reports: list[Wave9AssignmentExecutionReport] = []
        writes_by_path: dict[str, list[str]] = {}
        write_payloads: list[tuple[str, str, str]] = []
        reasons = ["wave9_task_pack_authorization_applies", "wave9_real_multi_worker_dry_run_only"]

        for assignment in task_pack.assignments:
            result = self._profile_runner.run(
                ProfileRunRequest(
                    profile=assignment.profile_id,
                    role=assignment.role,
                    prompt=_wave9_assignment_prompt(project_name=project_name, task_pack=task_pack, assignment=assignment),
                    source_ids=(task_pack.task_pack_id, assignment.assignment_id),
                )
            )
            provider_call_count += 1
            if result.exit_code != 0:
                assignment_reports.append(
                    Wave9AssignmentExecutionReport(
                        assignment_id=assignment.assignment_id,
                        profile_id=assignment.profile_id,
                        role=assignment.role,
                        status="failed",
                        exit_code=result.exit_code,
                        reason_codes=["profile_run_failed"],
                    )
                )
                report = _wave9_report(
                    run_id=run_id,
                    task_pack=task_pack,
                    status=Wave9ExecutionStatus.FAILED,
                    authorization_applies=True,
                    approval_id=authorization.approval_id if authorization else None,
                    provider_call_count=provider_call_count,
                    reason_codes=[*reasons, "profile_run_failed"],
                    assignment_reports=assignment_reports,
                    sandbox_path=str(sandbox),
                    source_repo_clean=_source_clean(source),
                )
                write_wave9_execution_evidence(report, root)
                return report
            try:
                writes = _parse_candidate_writes(result.stdout)
            except ValueError as exc:
                assignment_reports.append(
                    Wave9AssignmentExecutionReport(
                        assignment_id=assignment.assignment_id,
                        profile_id=assignment.profile_id,
                        role=assignment.role,
                        status="failed",
                        exit_code=result.exit_code,
                        reason_codes=[f"candidate_write_parse_failed:{exc}"],
                    )
                )
                report = _wave9_report(
                    run_id=run_id,
                    task_pack=task_pack,
                    status=Wave9ExecutionStatus.FAILED,
                    authorization_applies=True,
                    approval_id=authorization.approval_id if authorization else None,
                    provider_call_count=provider_call_count,
                    reason_codes=[*reasons, "candidate_write_parse_failed"],
                    assignment_reports=assignment_reports,
                    sandbox_path=str(sandbox),
                    source_repo_clean=_source_clean(source),
                )
                write_wave9_execution_evidence(report, root)
                return report
            candidate_files = [write.path for write in writes]
            allowed_scope = all(_path_allowed(write.path, assignment.allowed_files) for write in writes)
            assignment_reports.append(
                Wave9AssignmentExecutionReport(
                    assignment_id=assignment.assignment_id,
                    profile_id=assignment.profile_id,
                    role=assignment.role,
                    status="candidate_ready" if allowed_scope else "blocked",
                    candidate_files=candidate_files,
                    allowed_scope=allowed_scope,
                    exit_code=result.exit_code,
                    reason_codes=["candidate_writes_scope_ok"] if allowed_scope else ["candidate_write_outside_assignment_scope"],
                )
            )
            if not allowed_scope:
                report = _wave9_report(
                    run_id=run_id,
                    task_pack=task_pack,
                    status=Wave9ExecutionStatus.BLOCKED,
                    authorization_applies=True,
                    approval_id=authorization.approval_id if authorization else None,
                    provider_call_count=provider_call_count,
                    reason_codes=[*reasons, "candidate_write_outside_assignment_scope"],
                    assignment_reports=assignment_reports,
                    sandbox_path=str(sandbox),
                    source_repo_clean=_source_clean(source),
                )
                write_wave9_execution_evidence(report, root)
                return report
            for write in writes:
                writes_by_path.setdefault(write.path, []).append(assignment.assignment_id)
                write_payloads.append((assignment.assignment_id, write.path, write.content))

        conflict_files = sorted(path for path, assignment_ids in writes_by_path.items() if len(assignment_ids) > 1)
        if conflict_files and task_pack.merge_strategy == "reject_on_conflict":
            report = _wave9_report(
                run_id=run_id,
                task_pack=task_pack,
                status=Wave9ExecutionStatus.BLOCKED,
                authorization_applies=True,
                approval_id=authorization.approval_id if authorization else None,
                provider_call_count=provider_call_count,
                reason_codes=[*reasons, "merge_conflict_reject_on_conflict"],
                assignment_reports=assignment_reports,
                conflict_files=conflict_files,
                sandbox_path=str(sandbox),
                source_repo_clean=_source_clean(source),
            )
            write_wave9_execution_evidence(report, root)
            return report

        for _assignment_id, path, content in write_payloads:
            target = sandbox / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        verifier_outputs = _run_verifiers(sandbox, task_pack.verifier_commands)
        verifier_passed = all(item["exit_code"] == 0 for item in verifier_outputs)
        report = _wave9_report(
            run_id=run_id,
            task_pack=task_pack,
            status=Wave9ExecutionStatus.VERIFIED if verifier_passed else Wave9ExecutionStatus.FAILED,
            authorization_applies=True,
            approval_id=authorization.approval_id if authorization else None,
            provider_call_count=provider_call_count,
            reason_codes=[*reasons, "combined_verifier_passed"] if verifier_passed else [*reasons, "combined_verifier_failed"],
            assignment_reports=assignment_reports,
            conflict_files=conflict_files,
            verifier_outputs=verifier_outputs,
            sandbox_path=str(sandbox),
            source_repo_clean=_source_clean(source),
        )
        write_wave9_execution_evidence(report, root)
        return report


def task_pack_hash(pack: Wave9TaskPack) -> str:
    payload = pack.model_dump(mode="json")
    payload["task_pack_hash"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wave9_task_pack_path(project_root: str | Path, task_pack_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-task-packs" / task_pack_id / "task-pack.json"


def wave9_task_pack_authorization_path(project_root: str | Path, task_pack_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-task-packs" / task_pack_id / "authorization.json"


def approve_wave9_task_pack_execution(
    *,
    project_root: str | Path,
    task_pack: Wave9TaskPack,
    approval_id: str,
    approved_by: str,
    reason: str,
    max_total_profile_calls: int,
) -> Wave9TaskPackAuthorization:
    authorization = Wave9TaskPackAuthorization(
        approval_id=approval_id,
        approved_by=approved_by,
        task_pack_id=task_pack.task_pack_id,
        task_id=task_pack.task_id,
        approved_action="execute_wave9_real_multi_worker_dry_run",
        task_pack_hash=task_pack_hash(task_pack),
        worker_profile_ids=[assignment.profile_id for assignment in task_pack.assignments],
        verifier_commands=task_pack.verifier_commands,
        merge_strategy=task_pack.merge_strategy,
        dry_run_only=True,
        max_total_profile_calls=max_total_profile_calls,
        provider_call_count=0,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason=reason,
    )
    path = wave9_task_pack_authorization_path(project_root, task_pack.task_pack_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(authorization.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return authorization


def read_wave9_task_pack_authorization(project_root: str | Path, task_pack_id: str) -> Wave9TaskPackAuthorization:
    path = wave9_task_pack_authorization_path(project_root, task_pack_id)
    return Wave9TaskPackAuthorization.model_validate_json(path.read_text(encoding="utf-8"))


def validate_wave9_task_pack_authorization(
    *,
    pack: Wave9TaskPack,
    authorization: Wave9TaskPackAuthorization | None,
) -> Wave9AuthorizationCheck:
    expected_hash = task_pack_hash(pack)
    expected_workers = [assignment.profile_id for assignment in pack.assignments]
    reasons: list[str] = []
    if authorization is None:
        reasons.append("missing_wave9_task_pack_authorization")
    else:
        if authorization.task_pack_id != pack.task_pack_id:
            reasons.append("task_pack_id_mismatch")
        if authorization.task_id != pack.task_id:
            reasons.append("task_id_mismatch")
        if authorization.approved_action != "execute_wave9_real_multi_worker_dry_run":
            reasons.append("approved_action_mismatch")
        if authorization.task_pack_hash != expected_hash:
            reasons.append("task_pack_hash_mismatch")
        if authorization.worker_profile_ids != expected_workers:
            reasons.append("worker_profile_ids_mismatch")
        if authorization.verifier_commands != pack.verifier_commands:
            reasons.append("verifier_commands_mismatch")
        if authorization.merge_strategy != pack.merge_strategy:
            reasons.append("merge_strategy_mismatch")
        if authorization.dry_run_only is not True:
            reasons.append("authorization_not_dry_run_only")
        if authorization.provider_call_count != 0:
            reasons.append("authorization_indicates_provider_calls")
        if authorization.promotion_attempted:
            reasons.append("authorization_indicates_promotion_attempted")
        if authorization.global_hermes_config_mutated:
            reasons.append("authorization_indicates_global_hermes_config_mutation")
        if authorization.production_mutated:
            reasons.append("authorization_indicates_production_mutation")
    authorized = not reasons
    return Wave9AuthorizationCheck(
        task_pack_id=pack.task_pack_id,
        status=Wave9AuthorizationCheckStatus.AUTHORIZED if authorized else Wave9AuthorizationCheckStatus.BLOCKED,
        authorization_applies=authorized,
        approval_id=authorization.approval_id if authorization else None,
        approved_action=authorization.approved_action if authorization else None,
        task_pack_hash=expected_hash,
        worker_profile_ids=expected_workers,
        verifier_commands=pack.verifier_commands,
        merge_strategy=pack.merge_strategy,
        dry_run_only=True,
        max_total_profile_calls=authorization.max_total_profile_calls if authorization else 0,
        provider_call_count=0,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        reason_codes=["wave9_task_pack_authorization_applies", "provider_calls_not_started"] if authorized else reasons,
    )


def write_wave9_task_pack(pack: Wave9TaskPack, project_root: str | Path) -> Path:
    pack_with_hash = pack.model_copy(update={"task_pack_hash": task_pack_hash(pack)})
    path = wave9_task_pack_path(project_root, pack.task_pack_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack_with_hash.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_wave9_task_pack(project_root: str | Path, task_pack_id: str) -> Wave9TaskPack:
    path = wave9_task_pack_path(project_root, task_pack_id)
    return Wave9TaskPack.model_validate_json(path.read_text(encoding="utf-8"))


def wave9_execution_evidence_path(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-real-multi-worker-runs" / run_id / "evidence.json"


def wave9_execution_sandbox_path(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-real-multi-worker-runs" / run_id / "sandbox"


def write_wave9_execution_evidence(report: Wave9ExecutionReport, project_root: str | Path) -> Path:
    path = wave9_execution_evidence_path(project_root, report.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_wave9_execution_evidence(project_root: str | Path, run_id: str) -> Wave9ExecutionReport:
    path = wave9_execution_evidence_path(project_root, run_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("written_at", None)
    return Wave9ExecutionReport.model_validate(payload)


def wave9_local_pr_plan_path(project_root: str | Path, plan_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-local-pr-plans" / plan_id / "pr-plan.json"


def create_wave9_local_pr_plan(
    *,
    project_root: str | Path,
    execution_report: Wave9ExecutionReport,
    plan_id: str,
    target_branch: str,
    title: str,
) -> Wave9LocalPRPlan:
    changed_files = sorted(
        {
            candidate_file
            for assignment in execution_report.assignment_reports
            for candidate_file in assignment.candidate_files
        }
    )
    verified = (
        execution_report.status is Wave9ExecutionStatus.VERIFIED
        and execution_report.dry_run_only
        and not execution_report.promotion_attempted
        and not execution_report.external_pr_created
        and not execution_report.merge_performed
        and not execution_report.deploy_performed
        and not execution_report.global_hermes_config_mutated
        and not execution_report.production_mutated
        and execution_report.source_repo_clean
    )
    reason_codes = (
        ["wave9_verified_execution_evidence_applies", "local_pr_plan_only", "provider_calls_not_started"]
        if verified
        else ["execution_not_verified", "local_pr_plan_blocked", "provider_calls_not_started"]
    )
    plan = Wave9LocalPRPlan(
        plan_id=plan_id,
        execution_run_id=execution_report.run_id,
        task_pack_id=execution_report.task_pack_id,
        task_id=execution_report.task_id,
        status=Wave9LocalPRPlanStatus.PLANNED if verified else Wave9LocalPRPlanStatus.BLOCKED,
        target_branch=target_branch,
        title=title,
        changed_files=changed_files if verified else [],
        verifier_commands=[str(item.get("command", "")) for item in execution_report.verifier_outputs if item.get("command")],
        review_checklist=[
            "Review sandbox diff before any branch copy.",
            "Re-run verifier commands in a dedicated PR worktree before opening an external PR.",
            "Keep external PR creation, merge, deploy, promotion, and production mutation disabled until separately authorized.",
        ],
        provider_call_count=0,
        reason_codes=reason_codes,
        dry_run_only=True,
        promotion_attempted=False,
        external_pr_created=False,
        merge_performed=False,
        deploy_performed=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        source_repo_clean=execution_report.source_repo_clean,
    )
    path = wave9_local_pr_plan_path(project_root, plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def read_wave9_local_pr_plan(project_root: str | Path, plan_id: str) -> Wave9LocalPRPlan:
    return Wave9LocalPRPlan.model_validate_json(wave9_local_pr_plan_path(project_root, plan_id).read_text(encoding="utf-8"))


def wave9_local_pr_plan_hash(plan: Wave9LocalPRPlan) -> str:
    canonical = json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wave9_local_branch_materialization_approval_path(project_root: str | Path, plan_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-local-pr-plans" / plan_id / "materialization-approval.json"


def wave9_local_branch_materialization_path(project_root: str | Path, materialization_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-local-branch-materializations" / materialization_id / "evidence.json"


def approve_wave9_local_pr_plan_materialization(
    *,
    project_root: str | Path,
    plan: Wave9LocalPRPlan,
    approval_id: str,
    approved_by: str,
    reason: str,
) -> Wave9LocalBranchMaterializationApproval:
    approval = Wave9LocalBranchMaterializationApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        approved_action="materialize_wave9_local_pr_plan",
        plan_id=plan.plan_id,
        execution_run_id=plan.execution_run_id,
        plan_hash=wave9_local_pr_plan_hash(plan),
        target_branch=plan.target_branch,
        changed_files=plan.changed_files,
        verifier_commands=plan.verifier_commands,
        local_only=True,
        provider_call_count=0,
        external_pr_created=False,
        branch_pushed=False,
        merge_performed=False,
        deploy_performed=False,
        production_mutated=False,
        reason=reason,
    )
    path = wave9_local_branch_materialization_approval_path(project_root, plan.plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approval.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return approval


def read_wave9_local_branch_materialization_approval(project_root: str | Path, plan_id: str) -> Wave9LocalBranchMaterializationApproval:
    return Wave9LocalBranchMaterializationApproval.model_validate_json(
        wave9_local_branch_materialization_approval_path(project_root, plan_id).read_text(encoding="utf-8")
    )


def read_wave9_local_branch_materialization(project_root: str | Path, materialization_id: str) -> Wave9LocalBranchMaterialization:
    return Wave9LocalBranchMaterialization.model_validate_json(
        wave9_local_branch_materialization_path(project_root, materialization_id).read_text(encoding="utf-8")
    )


def materialize_wave9_local_pr_plan(
    *,
    project_root: str | Path,
    source_repo: str | Path,
    plan: Wave9LocalPRPlan,
    approval: Wave9LocalBranchMaterializationApproval | None,
    materialization_id: str,
    worktree_path: str | Path,
) -> Wave9LocalBranchMaterialization:
    root = Path(project_root)
    source = Path(source_repo)
    worktree = Path(worktree_path)
    reasons = _wave9_materialization_block_reasons(plan=plan, approval=approval)
    if reasons:
        evidence = Wave9LocalBranchMaterialization(
            materialization_id=materialization_id,
            plan_id=plan.plan_id,
            execution_run_id=plan.execution_run_id,
            status=Wave9LocalBranchMaterializationStatus.BLOCKED,
            approval_id=approval.approval_id if approval else None,
            local_branch_name=plan.target_branch,
            worktree_path=str(worktree),
            changed_files=[],
            verifier_outputs=[],
            provider_call_count=0,
            reason_codes=reasons,
            local_branch_created=False,
            branch_pushed=False,
            external_pr_created=False,
            merge_performed=False,
            deploy_performed=False,
            promotion_attempted=False,
            global_hermes_config_mutated=False,
            production_mutated=False,
            source_repo_clean=_source_clean(source),
        )
        _write_wave9_materialization_evidence(root, evidence)
        return evidence

    execution_report = read_wave9_execution_evidence(root, plan.execution_run_id)
    sandbox = Path(execution_report.sandbox_path or "")
    if not sandbox.exists():
        evidence = Wave9LocalBranchMaterialization(
            materialization_id=materialization_id,
            plan_id=plan.plan_id,
            execution_run_id=plan.execution_run_id,
            status=Wave9LocalBranchMaterializationStatus.BLOCKED,
            approval_id=approval.approval_id if approval else None,
            local_branch_name=plan.target_branch,
            worktree_path=str(worktree),
            changed_files=[],
            verifier_outputs=[],
            provider_call_count=0,
            reason_codes=["missing_wave9_execution_sandbox"],
            source_repo_clean=_source_clean(source),
        )
        _write_wave9_materialization_evidence(root, evidence)
        return evidence

    if worktree.exists():
        shutil.rmtree(worktree)
    subprocess.run(["git", "worktree", "add", "-B", plan.target_branch, str(worktree)], cwd=source, check=True, capture_output=True, text=True)
    copied: list[str] = []
    for changed_file in plan.changed_files:
        src = sandbox / changed_file
        dst = worktree / changed_file
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(changed_file)
    verifier_outputs = _run_verifiers(worktree, plan.verifier_commands)
    verified = bool(copied) and len(copied) == len(plan.changed_files) and all(item["exit_code"] == 0 for item in verifier_outputs)
    evidence = Wave9LocalBranchMaterialization(
        materialization_id=materialization_id,
        plan_id=plan.plan_id,
        execution_run_id=plan.execution_run_id,
        status=Wave9LocalBranchMaterializationStatus.VERIFIED if verified else Wave9LocalBranchMaterializationStatus.FAILED,
        approval_id=approval.approval_id if approval else None,
        local_branch_name=plan.target_branch,
        worktree_path=str(worktree),
        changed_files=copied,
        verifier_outputs=verifier_outputs,
        provider_call_count=0,
        reason_codes=["wave9_local_branch_materialization_approval_applies", "local_branch_materialized", "local_verifier_passed"] if verified else ["wave9_local_branch_materialization_approval_applies", "local_branch_materialized", "local_verifier_failed"],
        local_branch_created=True,
        branch_pushed=False,
        external_pr_created=False,
        merge_performed=False,
        deploy_performed=False,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        source_repo_clean=_source_clean(source),
    )
    _write_wave9_materialization_evidence(root, evidence)
    return evidence


def _wave9_materialization_block_reasons(*, plan: Wave9LocalPRPlan, approval: Wave9LocalBranchMaterializationApproval | None) -> list[str]:
    reasons: list[str] = []
    if plan.status is not Wave9LocalPRPlanStatus.PLANNED:
        reasons.append("wave9_local_pr_plan_not_planned")
    if plan.provider_call_count != 0 or plan.external_pr_created or plan.merge_performed or plan.deploy_performed or plan.production_mutated:
        reasons.append("wave9_local_pr_plan_not_local_only")
    if approval is None:
        reasons.append("missing_wave9_local_branch_materialization_approval")
    else:
        if approval.plan_id != plan.plan_id:
            reasons.append("plan_id_mismatch")
        if approval.execution_run_id != plan.execution_run_id:
            reasons.append("execution_run_id_mismatch")
        if approval.plan_hash != wave9_local_pr_plan_hash(plan):
            reasons.append("plan_hash_mismatch")
        if approval.target_branch != plan.target_branch:
            reasons.append("target_branch_mismatch")
        if approval.changed_files != plan.changed_files:
            reasons.append("changed_files_mismatch")
        if approval.verifier_commands != plan.verifier_commands:
            reasons.append("verifier_commands_mismatch")
        if approval.approved_action != "materialize_wave9_local_pr_plan":
            reasons.append("approved_action_mismatch")
        if not approval.local_only or approval.provider_call_count != 0 or approval.external_pr_created or approval.branch_pushed or approval.merge_performed or approval.deploy_performed or approval.production_mutated:
            reasons.append("approval_not_local_only")
    return reasons


def _write_wave9_materialization_evidence(project_root: str | Path, evidence: Wave9LocalBranchMaterialization) -> Path:
    path = wave9_local_branch_materialization_path(project_root, evidence.materialization_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def wave9_local_branch_materialization_hash(materialization: Wave9LocalBranchMaterialization) -> str:
    canonical = json.dumps(materialization.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wave9_local_branch_commit_approval_path(project_root: str | Path, materialization_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-local-branch-materializations" / materialization_id / "commit-approval.json"


def wave9_local_branch_commit_path(project_root: str | Path, commit_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-local-branch-commits" / commit_id / "evidence.json"


def approve_wave9_local_branch_commit(
    *,
    project_root: str | Path,
    materialization: Wave9LocalBranchMaterialization,
    approval_id: str,
    approved_by: str,
    reason: str,
) -> Wave9LocalBranchCommitApproval:
    approval = Wave9LocalBranchCommitApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        approved_action="commit_wave9_local_branch",
        materialization_id=materialization.materialization_id,
        materialization_hash=wave9_local_branch_materialization_hash(materialization),
        plan_id=materialization.plan_id,
        execution_run_id=materialization.execution_run_id,
        local_branch_name=materialization.local_branch_name,
        changed_files=materialization.changed_files,
        verifier_commands=[str(item.get("command", "")) for item in materialization.verifier_outputs if item.get("command")],
        local_only=True,
        provider_call_count=0,
        branch_pushed=False,
        external_pr_created=False,
        merge_performed=False,
        deploy_performed=False,
        production_mutated=False,
        reason=reason,
    )
    path = wave9_local_branch_commit_approval_path(project_root, materialization.materialization_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approval.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return approval


def read_wave9_local_branch_commit_approval(project_root: str | Path, materialization_id: str) -> Wave9LocalBranchCommitApproval:
    return Wave9LocalBranchCommitApproval.model_validate_json(
        wave9_local_branch_commit_approval_path(project_root, materialization_id).read_text(encoding="utf-8")
    )


def read_wave9_local_branch_commit(project_root: str | Path, commit_id: str) -> Wave9LocalBranchCommit:
    return Wave9LocalBranchCommit.model_validate_json(wave9_local_branch_commit_path(project_root, commit_id).read_text(encoding="utf-8"))


def commit_wave9_local_branch(
    *,
    project_root: str | Path,
    materialization: Wave9LocalBranchMaterialization,
    approval: Wave9LocalBranchCommitApproval | None,
    commit_id: str,
    commit_message: str,
) -> Wave9LocalBranchCommit:
    root = Path(project_root)
    worktree = Path(materialization.worktree_path or "")
    reasons = _wave9_commit_block_reasons(materialization=materialization, approval=approval)
    if reasons:
        evidence = _wave9_commit_evidence(
            commit_id=commit_id,
            materialization=materialization,
            status=Wave9LocalBranchCommitStatus.BLOCKED,
            approval_id=approval.approval_id if approval else None,
            local_commit_created=False,
            local_commit_sha=None,
            verifier_outputs=[],
            reason_codes=reasons,
        )
        _write_wave9_commit_evidence(root, evidence)
        return evidence

    verifier_outputs = _run_verifiers(worktree, approval.verifier_commands if approval else [])
    verifier_passed = all(item["exit_code"] == 0 for item in verifier_outputs)
    if not verifier_passed:
        evidence = _wave9_commit_evidence(
            commit_id=commit_id,
            materialization=materialization,
            status=Wave9LocalBranchCommitStatus.FAILED,
            approval_id=approval.approval_id if approval else None,
            local_commit_created=False,
            local_commit_sha=None,
            verifier_outputs=verifier_outputs,
            reason_codes=["wave9_local_branch_commit_approval_applies", "local_verifier_failed"],
        )
        _write_wave9_commit_evidence(root, evidence)
        return evidence

    subprocess.run(["git", "add", *materialization.changed_files], cwd=worktree, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", commit_message], cwd=worktree, check=True, capture_output=True, text=True)
    commit_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, text=True).strip()
    evidence = _wave9_commit_evidence(
        commit_id=commit_id,
        materialization=materialization,
        status=Wave9LocalBranchCommitStatus.COMMITTED,
        approval_id=approval.approval_id if approval else None,
        local_commit_created=True,
        local_commit_sha=commit_sha,
        verifier_outputs=verifier_outputs,
        reason_codes=["wave9_local_branch_commit_approval_applies", "local_verifier_passed", "local_branch_commit_created"],
    )
    _write_wave9_commit_evidence(root, evidence)
    return evidence


def _wave9_commit_block_reasons(*, materialization: Wave9LocalBranchMaterialization, approval: Wave9LocalBranchCommitApproval | None) -> list[str]:
    reasons: list[str] = []
    if materialization.status is not Wave9LocalBranchMaterializationStatus.VERIFIED:
        reasons.append("wave9_materialization_not_verified")
    if not materialization.local_branch_created or materialization.branch_pushed or materialization.external_pr_created or materialization.merge_performed or materialization.deploy_performed or materialization.production_mutated:
        reasons.append("wave9_materialization_not_local_only")
    if not materialization.worktree_path or not Path(materialization.worktree_path).exists():
        reasons.append("missing_wave9_materialization_worktree")
    if approval is None:
        reasons.append("missing_wave9_local_branch_commit_approval")
    else:
        if approval.materialization_id != materialization.materialization_id:
            reasons.append("materialization_id_mismatch")
        if approval.materialization_hash != wave9_local_branch_materialization_hash(materialization):
            reasons.append("materialization_hash_mismatch")
        if approval.plan_id != materialization.plan_id:
            reasons.append("plan_id_mismatch")
        if approval.execution_run_id != materialization.execution_run_id:
            reasons.append("execution_run_id_mismatch")
        if approval.local_branch_name != materialization.local_branch_name:
            reasons.append("local_branch_name_mismatch")
        if approval.changed_files != materialization.changed_files:
            reasons.append("changed_files_mismatch")
        if approval.approved_action != "commit_wave9_local_branch":
            reasons.append("approved_action_mismatch")
        if not approval.local_only or approval.provider_call_count != 0 or approval.branch_pushed or approval.external_pr_created or approval.merge_performed or approval.deploy_performed or approval.production_mutated:
            reasons.append("approval_not_local_only")
    return reasons


def _wave9_commit_evidence(
    *,
    commit_id: str,
    materialization: Wave9LocalBranchMaterialization,
    status: Wave9LocalBranchCommitStatus,
    approval_id: str | None,
    local_commit_created: bool,
    local_commit_sha: str | None,
    verifier_outputs: list[dict[str, object]],
    reason_codes: list[str],
) -> Wave9LocalBranchCommit:
    return Wave9LocalBranchCommit(
        commit_id=commit_id,
        materialization_id=materialization.materialization_id,
        plan_id=materialization.plan_id,
        execution_run_id=materialization.execution_run_id,
        status=status,
        approval_id=approval_id,
        local_branch_name=materialization.local_branch_name,
        worktree_path=materialization.worktree_path,
        changed_files=materialization.changed_files if local_commit_created else [],
        local_commit_created=local_commit_created,
        local_commit_sha=local_commit_sha,
        verifier_outputs=verifier_outputs,
        provider_call_count=0,
        reason_codes=reason_codes,
        branch_pushed=False,
        external_pr_created=False,
        merge_performed=False,
        deploy_performed=False,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
    )


def _write_wave9_commit_evidence(project_root: str | Path, evidence: Wave9LocalBranchCommit) -> Path:
    path = wave9_local_branch_commit_path(project_root, evidence.commit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path




def wave9_local_branch_commit_hash(commit: Wave9LocalBranchCommit) -> str:
    canonical = json.dumps(commit.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wave9_draft_pr_approval_path(project_root: str | Path, commit_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-draft-prs" / commit_id / "approval.json"


def wave9_draft_pr_evidence_path(project_root: str | Path, pr_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-draft-prs" / pr_id / "evidence.json"


def approve_wave9_draft_pr(
    *,
    project_root: str | Path,
    commit: Wave9LocalBranchCommit,
    approval_id: str,
    approved_by: str,
    target_branch: str,
    reason: str,
) -> Wave9DraftPRApproval:
    approval = Wave9DraftPRApproval(
        approval_id=approval_id,
        approved_by=approved_by,
        approved_action="create_wave9_draft_pr",
        commit_id=commit.commit_id,
        local_commit_sha=commit.local_commit_sha or "",
        local_branch_name=commit.local_branch_name,
        changed_files=commit.changed_files,
        commit_hash=wave9_local_branch_commit_hash(commit),
        target_branch=target_branch,
        draft_only=True,
        provider_call_count=0,
        branch_push_authorized=True,
        external_pr_creation_authorized=True,
        auto_merge_enabled=False,
        merge_performed=False,
        deploy_performed=False,
        production_mutated=False,
        reason=reason,
    )
    path = wave9_draft_pr_approval_path(project_root, commit.commit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approval.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return approval


def read_wave9_draft_pr_approval(project_root: str | Path, commit_id: str) -> Wave9DraftPRApproval:
    return Wave9DraftPRApproval.model_validate_json(wave9_draft_pr_approval_path(project_root, commit_id).read_text(encoding="utf-8"))


def read_wave9_draft_pr_evidence(project_root: str | Path, pr_id: str) -> Wave9DraftPR:
    return Wave9DraftPR.model_validate_json(wave9_draft_pr_evidence_path(project_root, pr_id).read_text(encoding="utf-8"))


def create_wave9_draft_pr(
    *,
    project_root: str | Path,
    commit: Wave9LocalBranchCommit,
    approval: Wave9DraftPRApproval | None,
    pr_id: str,
    target_branch: str,
    adapter: Wave9DraftPRAdapter | None = None,
) -> Wave9DraftPR:
    reasons = _wave9_draft_pr_block_reasons(commit=commit, approval=approval, target_branch=target_branch)
    if reasons:
        evidence = _wave9_draft_pr_evidence(
            pr_id=pr_id,
            commit=commit,
            target_branch=target_branch,
            status=Wave9DraftPRStatus.BLOCKED,
            approval_applies=False,
            approval_id=approval.approval_id if approval else None,
            adapter_name=(adapter or Wave9DraftPRAdapter()).name,
            created={},
            reason_codes=reasons,
        )
        _write_wave9_draft_pr_evidence(project_root, evidence)
        return evidence
    adapter = adapter or Wave9DraftPRAdapter()
    title = f"Wave9 real multi-worker result: {commit.commit_id}"
    body = "\n".join([
        "# Wave9 real multi-worker Draft PR",
        "",
        f"commit_id: {commit.commit_id}",
        f"materialization_id: {commit.materialization_id}",
        f"execution_run_id: {commit.execution_run_id}",
        f"local_commit_sha: {commit.local_commit_sha}",
        f"changed_files: {', '.join(commit.changed_files)}",
        "",
        "Safety flags:",
        "- draft: true",
        "- auto_merge_enabled: false",
        "- merge_performed: false",
        "- deploy_performed: false",
        "- production_mutated: false",
    ])
    try:
        created = adapter.create_draft_pr(source_branch=commit.local_branch_name, target_branch=target_branch, title=title, body=body)
        reasons = ["wave9_draft_pr_approval_applies", "github_draft_pr_created"] if created.get("external_pr_created") else ["wave9_draft_pr_approval_applies", "fake_adapter_no_external_pr_created"]
        evidence = _wave9_draft_pr_evidence(
            pr_id=pr_id,
            commit=commit,
            target_branch=target_branch,
            status=Wave9DraftPRStatus.CREATED,
            approval_applies=True,
            approval_id=approval.approval_id if approval else None,
            adapter_name=adapter.name,
            created=created,
            reason_codes=reasons,
        )
    except Exception as exc:
        evidence = _wave9_draft_pr_evidence(
            pr_id=pr_id,
            commit=commit,
            target_branch=target_branch,
            status=Wave9DraftPRStatus.FAILED,
            approval_applies=True,
            approval_id=approval.approval_id if approval else None,
            adapter_name=adapter.name,
            created={},
            reason_codes=["wave9_draft_pr_approval_applies", f"draft_pr_adapter_failed:{exc}"],
        )
    _write_wave9_draft_pr_evidence(project_root, evidence)
    return evidence


def _wave9_draft_pr_block_reasons(*, commit: Wave9LocalBranchCommit, approval: Wave9DraftPRApproval | None, target_branch: str) -> list[str]:
    reasons: list[str] = []
    if commit.status is not Wave9LocalBranchCommitStatus.COMMITTED or not commit.local_commit_created or not commit.local_commit_sha:
        reasons.append("wave9_local_branch_commit_not_committed")
    if commit.branch_pushed or commit.external_pr_created or commit.merge_performed or commit.deploy_performed or commit.production_mutated:
        reasons.append("wave9_local_branch_commit_not_pre_external_pr")
    if not commit.worktree_path or not Path(commit.worktree_path).exists():
        reasons.append("missing_wave9_commit_worktree")
    if approval is None:
        reasons.append("missing_wave9_draft_pr_approval")
    else:
        if approval.commit_id != commit.commit_id:
            reasons.append("commit_id_mismatch")
        if approval.local_commit_sha != commit.local_commit_sha:
            reasons.append("local_commit_sha_mismatch")
        if approval.local_branch_name != commit.local_branch_name:
            reasons.append("local_branch_name_mismatch")
        if approval.changed_files != commit.changed_files:
            reasons.append("changed_files_mismatch")
        if approval.commit_hash != wave9_local_branch_commit_hash(commit):
            reasons.append("commit_hash_mismatch")
        if approval.target_branch != target_branch:
            reasons.append("target_branch_mismatch")
        if approval.approved_action != "create_wave9_draft_pr":
            reasons.append("approved_action_mismatch")
        if not approval.draft_only or approval.provider_call_count != 0 or not approval.branch_push_authorized or not approval.external_pr_creation_authorized:
            reasons.append("approval_not_draft_pr_only")
        if approval.auto_merge_enabled or approval.merge_performed or approval.deploy_performed or approval.production_mutated:
            reasons.append("approval_attempts_unsafe_pr_side_effect")
    return reasons


def _wave9_draft_pr_evidence(
    *,
    pr_id: str,
    commit: Wave9LocalBranchCommit,
    target_branch: str,
    status: Wave9DraftPRStatus,
    approval_applies: bool,
    approval_id: str | None,
    adapter_name: str,
    created: dict[str, object],
    reason_codes: list[str],
) -> Wave9DraftPR:
    return Wave9DraftPR(
        pr_id=pr_id,
        commit_id=commit.commit_id,
        materialization_id=commit.materialization_id,
        plan_id=commit.plan_id,
        execution_run_id=commit.execution_run_id,
        status=status,
        approval_applies=approval_applies,
        approval_id=approval_id,
        local_branch_name=commit.local_branch_name,
        target_branch=target_branch,
        changed_files=commit.changed_files if approval_applies else [],
        local_commit_sha=commit.local_commit_sha,
        branch_pushed=bool(created.get("branch_pushed", False)),
        external_pr_created=bool(created.get("external_pr_created", False)),
        draft=bool(created.get("draft", True)),
        state=created.get("state") if isinstance(created.get("state"), str) else None,
        pr_number=created.get("pr_number") if isinstance(created.get("pr_number"), int) else None,
        pr_url=created.get("pr_url") if isinstance(created.get("pr_url"), str) else None,
        head_ref=created.get("head_ref") if isinstance(created.get("head_ref"), str) else None,
        base_ref=created.get("base_ref") if isinstance(created.get("base_ref"), str) else None,
        adapter=adapter_name,
        provider_call_count=0,
        reason_codes=reason_codes,
        auto_merge_enabled=bool(created.get("auto_merge", False)),
        merge_performed=False,
        deploy_performed=False,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
    )


def _write_wave9_draft_pr_evidence(project_root: str | Path, evidence: Wave9DraftPR) -> Path:
    path = wave9_draft_pr_evidence_path(project_root, evidence.pr_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _extract_wave9_pr_url(stdout: str) -> str | None:
    for token in stdout.replace("\n", " ").split():
        if token.startswith("https://github.com/") and "/pull/" in token:
            return token.strip()
    return None



def wave9_pr_semantic_review_path(project_root: str | Path, review_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-pr-reviews" / review_id / "evidence.json"


def wave9_capability_ingestion_path(project_root: str | Path, ingestion_id: str) -> Path:
    return Path(project_root) / ".hermes" / "wave9-capability-ingestions" / ingestion_id / "evidence.json"


def run_wave9_pr_semantic_review(
    *,
    project_root: str | Path,
    draft_pr: Wave9DraftPR,
    review_id: str,
    diff_text: str,
    required_terms: list[str],
    forbidden_terms: list[str],
) -> Wave9PRSemanticReview:
    missing = [term for term in required_terms if term not in diff_text]
    present = [term for term in forbidden_terms if term in diff_text]
    status = Wave9PRSemanticReviewStatus.PASSED if not missing and not present else Wave9PRSemanticReviewStatus.BLOCKED
    reasons = ["wave9_pr_diff_review_passed", "provider_free_review_only"] if status is Wave9PRSemanticReviewStatus.PASSED else [
        *[f"missing_required_term:{term}" for term in missing],
        *[f"forbidden_term_present:{term}" for term in present],
        "provider_free_review_only",
    ]
    review = Wave9PRSemanticReview(
        review_id=review_id,
        pr_id=draft_pr.pr_id,
        status=status,
        required_terms=required_terms,
        forbidden_terms=forbidden_terms,
        missing_required_terms=missing,
        present_forbidden_terms=present,
        provider_call_count=0,
        mutates_state=False,
        external_pr_mutated=False,
        merge_performed=False,
        deploy_performed=False,
        production_mutated=False,
        reason_codes=reasons,
    )
    path = wave9_pr_semantic_review_path(project_root, review_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return review


def read_wave9_pr_semantic_review(project_root: str | Path, review_id: str) -> Wave9PRSemanticReview:
    return Wave9PRSemanticReview.model_validate_json(wave9_pr_semantic_review_path(project_root, review_id).read_text(encoding="utf-8"))


def ingest_wave9_capability_evaluation(
    *,
    project_root: str | Path,
    ingestion_id: str,
    commit: Wave9LocalBranchCommit,
    draft_pr: Wave9DraftPR,
    semantic_review: Wave9PRSemanticReview,
) -> Wave9CapabilityIngestion:
    reasons: list[str] = []
    if commit.status is not Wave9LocalBranchCommitStatus.COMMITTED:
        reasons.append("wave9_commit_not_committed")
    if draft_pr.status is not Wave9DraftPRStatus.CREATED or not draft_pr.draft:
        reasons.append("wave9_draft_pr_not_created")
    if semantic_review.status is not Wave9PRSemanticReviewStatus.PASSED:
        reasons.append("wave9_semantic_review_not_passed")
    status = Wave9CapabilityIngestionStatus.INGESTED if not reasons else Wave9CapabilityIngestionStatus.BLOCKED
    if not reasons:
        reasons = ["wave9_capability_record_ingested", "wave9_evaluation_record_ingested", "routing_table_not_mutated"]
    ingestion = Wave9CapabilityIngestion(
        ingestion_id=ingestion_id,
        status=status,
        execution_run_id=commit.execution_run_id,
        commit_id=commit.commit_id,
        pr_id=draft_pr.pr_id,
        semantic_review_id=semantic_review.review_id,
        capability_record_written=status is Wave9CapabilityIngestionStatus.INGESTED,
        evaluation_record_written=status is Wave9CapabilityIngestionStatus.INGESTED,
        provider_call_count=0,
        routing_table_mutated=False,
        merge_performed=False,
        deploy_performed=False,
        production_mutated=False,
        reason_codes=reasons,
    )
    path = wave9_capability_ingestion_path(project_root, ingestion_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ingestion.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ingestion


def read_wave9_capability_ingestion(project_root: str | Path, ingestion_id: str) -> Wave9CapabilityIngestion:
    return Wave9CapabilityIngestion.model_validate_json(wave9_capability_ingestion_path(project_root, ingestion_id).read_text(encoding="utf-8"))

def _wave9_assignment_prompt(*, project_name: str, task_pack: Wave9TaskPack, assignment: Wave9TaskAssignment) -> str:
    return "\n".join(
        [
            "Produce JSON only with shape {\"writes\":[{\"path\":str,\"content\":str}] }.",
            f"Project: {project_name}",
            f"Task pack: {task_pack.task_pack_id}",
            f"Task ID: {task_pack.task_id}",
            f"Title: {task_pack.title}",
            f"Summary: {task_pack.summary}",
            f"Assignment: {assignment.assignment_id}",
            f"Role: {assignment.role}",
            f"Objective: {assignment.objective}",
            f"Allowed files: {', '.join(assignment.allowed_files)}",
            f"Verifier commands: {'; '.join(assignment.verifier_commands)}",
            "Do not include markdown fences or commentary.",
            "Do not modify global Hermes config, create PRs, merge, deploy, promote, or mutate production.",
        ]
    )


def _path_allowed(path: str, allowed_files: list[str]) -> bool:
    return any(path == allowed or path.startswith(f"{allowed.rstrip('/')}/") for allowed in allowed_files)


def _run_verifiers(cwd: Path, commands: list[str]) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for command in commands:
        completed = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True, check=False)
        outputs.append(
            {
                "command": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        )
    return outputs


def _source_clean(source_repo: Path) -> bool:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=source_repo, text=True, capture_output=True, check=False)
    return completed.returncode == 0 and completed.stdout == ""


def _wave9_report(
    *,
    run_id: str,
    task_pack: Wave9TaskPack,
    status: Wave9ExecutionStatus,
    authorization_applies: bool,
    approval_id: str | None,
    provider_call_count: int,
    reason_codes: list[str],
    assignment_reports: list[Wave9AssignmentExecutionReport] | None = None,
    conflict_files: list[str] | None = None,
    verifier_outputs: list[dict[str, object]] | None = None,
    sandbox_path: str | None = None,
    source_repo_clean: bool = True,
) -> Wave9ExecutionReport:
    return Wave9ExecutionReport(
        run_id=run_id,
        task_pack_id=task_pack.task_pack_id,
        task_id=task_pack.task_id,
        status=status,
        authorization_applies=authorization_applies,
        approval_id=approval_id,
        assignment_reports=assignment_reports or [],
        provider_call_count=provider_call_count,
        reason_codes=_dedupe(reason_codes),
        conflict_files=conflict_files or [],
        verifier_outputs=verifier_outputs or [],
        sandbox_path=sandbox_path,
        dry_run_only=True,
        promotion_attempted=False,
        external_pr_created=False,
        merge_performed=False,
        deploy_performed=False,
        global_hermes_config_mutated=False,
        production_mutated=False,
        source_repo_clean=source_repo_clean,
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
