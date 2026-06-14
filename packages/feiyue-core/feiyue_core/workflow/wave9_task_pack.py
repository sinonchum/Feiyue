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
