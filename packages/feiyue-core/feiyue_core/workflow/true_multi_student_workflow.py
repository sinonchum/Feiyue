from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from feiyue_core.providers.profile_runner import ProfileRunRequest
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.profile_worker_bridge import ProfileRunnerLike, _parse_candidate_writes
from feiyue_core.workflow.task_contract import TaskContract

AssignmentRole = Literal["implementation", "tests", "docs", "review", "verifier"]
MergeStrategy = Literal["reject_on_conflict", "ordered_overlay", "reviewer_selected_patch"]
VerifierStrategy = Literal["per_assignment_then_combined", "combined_only"]


class MultiStudentDryRunStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    BLOCKED = "blocked"


class MultiStudentAssignment(FeiyueModel):
    assignment_id: str
    profile_id: str
    role: AssignmentRole
    capabilities: list[str]
    allowed_files: list[str]
    max_profile_calls: int = Field(default=1, ge=1)
    depends_on_assignment_ids: list[str] = Field(default_factory=list)

    @field_validator("assignment_id", "profile_id", "role")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("assignment fields must be non-empty")
        return normalized

    @field_validator("capabilities", "allowed_files")
    @classmethod
    def _required_list(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("assignment lists must contain non-empty strings")
        return normalized


class MultiStudentPlan(FeiyueModel):
    plan_id: str
    task_id: str
    worker_assignments: list[MultiStudentAssignment]
    merge_strategy: MergeStrategy = "reject_on_conflict"
    verifier_strategy: VerifierStrategy = "per_assignment_then_combined"
    dry_run_only: bool = True
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    reason_codes: list[str]

    @field_validator("plan_id", "task_id")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("plan fields must be non-empty")
        return normalized

    @field_validator("worker_assignments")
    @classmethod
    def _at_least_two_assignments(cls, value: list[MultiStudentAssignment]) -> list[MultiStudentAssignment]:
        if len(value) < 2:
            raise ValueError("true multi-student plans require at least two assignments")
        return value

    @field_validator("reason_codes")
    @classmethod
    def _required_reasons(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("reason_codes must contain non-empty strings")
        return normalized


class MultiStudentDryRunApproval(FeiyueModel):
    approval_id: str
    approved_by: str
    plan_id: str
    task_id: str
    approved_action: str
    worker_assignment_hash: str
    worker_profile_ids: list[str]
    merge_strategy: MergeStrategy
    verifier_strategy: VerifierStrategy
    dry_run_only: bool = True
    max_total_profile_calls: int = Field(ge=0)
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator("approval_id", "approved_by", "plan_id", "task_id", "approved_action", "worker_assignment_hash", "reason")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("approval fields must be non-empty")
        return normalized

    @field_validator("worker_profile_ids")
    @classmethod
    def _required_profiles(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if not normalized or any(not item for item in normalized):
            raise ValueError("worker_profile_ids must contain non-empty strings")
        return normalized


class MultiStudentAssignmentReport(FeiyueModel):
    assignment_id: str
    profile_id: str
    role: str
    status: str
    candidate_files: list[str] = Field(default_factory=list)
    allowed_scope: bool = True
    exit_code: int = 0
    reason_codes: list[str] = Field(default_factory=list)


class MultiStudentDryRunReport(FeiyueModel):
    run_id: str
    task_id: str
    plan_id: str
    status: MultiStudentDryRunStatus
    assignment_reports: list[MultiStudentAssignmentReport] = Field(default_factory=list)
    provider_call_count: int = Field(default=0, ge=0)
    reason_codes: list[str]
    merge_strategy: MergeStrategy
    verifier_strategy: VerifierStrategy
    conflict_files: list[str] = Field(default_factory=list)
    verifier_outputs: list[dict[str, object]] = Field(default_factory=list)
    dry_run_only: bool = True
    promotion_attempted: bool = False
    global_hermes_config_mutated: bool = False
    source_repo_clean: bool = True


class MultiStudentDryRunExecutor:
    def __init__(self, *, profile_runner: ProfileRunnerLike) -> None:
        self._profile_runner = profile_runner

    def run(
        self,
        *,
        project_root: str | Path,
        source_repo: str | Path,
        project_name: str,
        contract: TaskContract,
        plan: MultiStudentPlan,
        approval: MultiStudentDryRunApproval | None,
        run_id: str,
    ) -> MultiStudentDryRunReport:
        root = Path(project_root)
        source = Path(source_repo)
        block_reasons = _approval_block_reasons(plan=plan, contract=contract, approval=approval)
        if block_reasons:
            report = _report(
                run_id=run_id,
                contract=contract,
                plan=plan,
                status=MultiStudentDryRunStatus.BLOCKED,
                provider_call_count=0,
                reason_codes=block_reasons,
                source_repo_clean=_source_clean(source),
            )
            write_multi_student_evidence(report, root)
            return report

        sandbox = root / ".hermes" / "multi-student-workflows" / run_id / "sandbox"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        ignore = shutil.ignore_patterns(".git", ".hermes", "__pycache__", ".pytest_cache")
        shutil.copytree(source, sandbox, ignore=ignore)

        provider_call_count = 0
        assignment_reports: list[MultiStudentAssignmentReport] = []
        writes_by_path: dict[str, list[str]] = {}
        write_payloads: list[tuple[MultiStudentAssignment, str, str]] = []
        reasons = ["true_multi_student_approval_applies", "true_multi_student_dry_run_only", *plan.reason_codes]

        for assignment in plan.worker_assignments:
            result = self._profile_runner.run(
                ProfileRunRequest(
                    profile=assignment.profile_id,
                    role=assignment.role,
                    prompt=_assignment_prompt(project_name=project_name, contract=contract, assignment=assignment),
                    source_ids=(plan.plan_id, assignment.assignment_id),
                )
            )
            provider_call_count += 1
            if result.exit_code != 0:
                assignment_reports.append(
                    MultiStudentAssignmentReport(
                        assignment_id=assignment.assignment_id,
                        profile_id=assignment.profile_id,
                        role=assignment.role,
                        status="failed",
                        exit_code=result.exit_code,
                        reason_codes=["profile_run_failed"],
                    )
                )
                report = _report(
                    run_id=run_id,
                    contract=contract,
                    plan=plan,
                    status=MultiStudentDryRunStatus.FAILED,
                    provider_call_count=provider_call_count,
                    reason_codes=[*reasons, "profile_run_failed"],
                    assignment_reports=assignment_reports,
                    source_repo_clean=_source_clean(source),
                )
                write_multi_student_evidence(report, root)
                return report
            try:
                writes = _parse_candidate_writes(result.stdout)
            except ValueError as exc:
                assignment_reports.append(
                    MultiStudentAssignmentReport(
                        assignment_id=assignment.assignment_id,
                        profile_id=assignment.profile_id,
                        role=assignment.role,
                        status="failed",
                        exit_code=result.exit_code,
                        reason_codes=[f"candidate_write_parse_failed:{exc}"],
                    )
                )
                report = _report(
                    run_id=run_id,
                    contract=contract,
                    plan=plan,
                    status=MultiStudentDryRunStatus.FAILED,
                    provider_call_count=provider_call_count,
                    reason_codes=[*reasons, "candidate_write_parse_failed"],
                    assignment_reports=assignment_reports,
                    source_repo_clean=_source_clean(source),
                )
                write_multi_student_evidence(report, root)
                return report
            candidate_files = [write.path for write in writes]
            allowed_scope = all(_path_allowed(write.path, assignment.allowed_files) for write in writes)
            assignment_reports.append(
                MultiStudentAssignmentReport(
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
                report = _report(
                    run_id=run_id,
                    contract=contract,
                    plan=plan,
                    status=MultiStudentDryRunStatus.BLOCKED,
                    provider_call_count=provider_call_count,
                    reason_codes=[*reasons, "candidate_write_outside_assignment_scope"],
                    assignment_reports=assignment_reports,
                    source_repo_clean=_source_clean(source),
                )
                write_multi_student_evidence(report, root)
                return report
            for write in writes:
                writes_by_path.setdefault(write.path, []).append(assignment.assignment_id)
                write_payloads.append((assignment, write.path, write.content))

        conflict_files = sorted(path for path, assignment_ids in writes_by_path.items() if len(assignment_ids) > 1)
        if conflict_files and plan.merge_strategy == "reject_on_conflict":
            report = _report(
                run_id=run_id,
                contract=contract,
                plan=plan,
                status=MultiStudentDryRunStatus.BLOCKED,
                provider_call_count=provider_call_count,
                reason_codes=[*reasons, "merge_conflict_reject_on_conflict"],
                assignment_reports=assignment_reports,
                conflict_files=conflict_files,
                source_repo_clean=_source_clean(source),
            )
            write_multi_student_evidence(report, root)
            return report

        for _assignment, path, content in write_payloads:
            target = sandbox / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        verifier_outputs = _run_verifiers(sandbox, contract.verification_commands)
        verifier_passed = all(item["exit_code"] == 0 for item in verifier_outputs)
        status = MultiStudentDryRunStatus.VERIFIED if verifier_passed else MultiStudentDryRunStatus.FAILED
        report = _report(
            run_id=run_id,
            contract=contract,
            plan=plan,
            status=status,
            provider_call_count=provider_call_count,
            reason_codes=[*reasons, "combined_verifier_passed"] if verifier_passed else [*reasons, "combined_verifier_failed"],
            assignment_reports=assignment_reports,
            conflict_files=conflict_files,
            verifier_outputs=verifier_outputs,
            source_repo_clean=_source_clean(source),
        )
        write_multi_student_evidence(report, root)
        return report


def assignment_hash(assignments: list[MultiStudentAssignment]) -> str:
    payload = [assignment.model_dump(mode="json") for assignment in assignments]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def multi_student_plan_path(project_root: str | Path, plan_id: str) -> Path:
    return Path(project_root) / ".hermes" / "multi-student-plans" / plan_id / "plan.json"


def multi_student_approval_path(project_root: str | Path, plan_id: str) -> Path:
    return Path(project_root) / ".hermes" / "multi-student-plans" / plan_id / "approval.json"


def write_multi_student_plan(plan: MultiStudentPlan, project_root: str | Path) -> Path:
    path = multi_student_plan_path(project_root, plan.plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_multi_student_plan(project_root: str | Path, plan_id: str) -> MultiStudentPlan:
    path = multi_student_plan_path(project_root, plan_id)
    if not path.exists():
        raise FileNotFoundError(f"true multi-student plan not found for plan_id: {plan_id}")
    return MultiStudentPlan.model_validate_json(path.read_text(encoding="utf-8"))


def write_multi_student_approval(approval: MultiStudentDryRunApproval, project_root: str | Path) -> Path:
    path = multi_student_approval_path(project_root, approval.plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(approval.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_multi_student_approval(project_root: str | Path, plan_id: str) -> MultiStudentDryRunApproval:
    path = multi_student_approval_path(project_root, plan_id)
    if not path.exists():
        raise FileNotFoundError(f"true multi-student approval not found for plan_id: {plan_id}")
    return MultiStudentDryRunApproval.model_validate_json(path.read_text(encoding="utf-8"))


def multi_student_evidence_path(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root) / ".hermes" / "multi-student-workflows" / run_id / "evidence.json"


def write_multi_student_evidence(report: MultiStudentDryRunReport, project_root: str | Path) -> Path:
    evidence_path = multi_student_evidence_path(project_root, report.run_id)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json") | {"written_at": datetime.now(UTC).isoformat()}
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (evidence_path.parent / "report.md").write_text(_render_report(report), encoding="utf-8")
    return evidence_path


def read_multi_student_evidence(project_root: str | Path, run_id: str) -> MultiStudentDryRunReport:
    path = multi_student_evidence_path(project_root, run_id)
    if not path.exists():
        raise FileNotFoundError(f"true multi-student workflow evidence not found for run_id: {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("written_at", None)
    return MultiStudentDryRunReport.model_validate(payload)


def _approval_block_reasons(*, plan: MultiStudentPlan, contract: TaskContract, approval: MultiStudentDryRunApproval | None) -> list[str]:
    if approval is None:
        return ["missing_true_multi_student_approval"]
    reasons: list[str] = []
    if approval.plan_id != plan.plan_id:
        reasons.append("approval_plan_id_mismatch")
    if approval.task_id != plan.task_id or approval.task_id != contract.task_id:
        reasons.append("approval_task_id_mismatch")
    if approval.approved_action != "execute_true_multi_student_dry_run":
        reasons.append("approval_action_mismatch")
    if approval.worker_assignment_hash != assignment_hash(plan.worker_assignments):
        reasons.append("approval_assignment_hash_mismatch")
    if approval.worker_profile_ids != [assignment.profile_id for assignment in plan.worker_assignments]:
        reasons.append("approval_worker_profile_ids_mismatch")
    if approval.merge_strategy != plan.merge_strategy:
        reasons.append("approval_merge_strategy_mismatch")
    if approval.verifier_strategy != plan.verifier_strategy:
        reasons.append("approval_verifier_strategy_mismatch")
    if not approval.dry_run_only or not plan.dry_run_only:
        reasons.append("approval_must_be_dry_run_only")
    if plan.promotion_attempted:
        reasons.append("plan_must_not_attempt_promotion")
    if plan.global_hermes_config_mutated:
        reasons.append("plan_must_not_mutate_global_hermes_config")
    if approval.max_total_profile_calls < len(plan.worker_assignments):
        reasons.append("max_total_profile_calls_would_be_exceeded")
    return reasons


def _assignment_prompt(*, project_name: str, contract: TaskContract, assignment: MultiStudentAssignment) -> str:
    return "\n".join(
        [
            "Produce JSON only with shape {\"writes\":[{\"path\":str,\"content\":str}] }.",
            f"Project: {project_name}",
            f"Task ID: {contract.task_id}",
            f"Title: {contract.title}",
            f"Assignment: {assignment.assignment_id}",
            f"Role: {assignment.role}",
            f"Allowed files: {', '.join(assignment.allowed_files)}",
            "Do not include markdown fences or commentary.",
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


def _report(
    *,
    run_id: str,
    contract: TaskContract,
    plan: MultiStudentPlan,
    status: MultiStudentDryRunStatus,
    provider_call_count: int,
    reason_codes: list[str],
    assignment_reports: list[MultiStudentAssignmentReport] | None = None,
    conflict_files: list[str] | None = None,
    verifier_outputs: list[dict[str, object]] | None = None,
    source_repo_clean: bool = True,
) -> MultiStudentDryRunReport:
    return MultiStudentDryRunReport(
        run_id=run_id,
        task_id=contract.task_id,
        plan_id=plan.plan_id,
        status=status,
        assignment_reports=assignment_reports or [],
        provider_call_count=provider_call_count,
        reason_codes=_dedupe(reason_codes),
        merge_strategy=plan.merge_strategy,
        verifier_strategy=plan.verifier_strategy,
        conflict_files=conflict_files or [],
        verifier_outputs=verifier_outputs or [],
        dry_run_only=True,
        promotion_attempted=False,
        global_hermes_config_mutated=False,
        source_repo_clean=source_repo_clean,
    )


def _render_report(report: MultiStudentDryRunReport) -> str:
    lines = [
        f"# True multi-student workflow: {report.run_id}",
        "",
        f"status: {report.status}",
        f"plan_id: {report.plan_id}",
        f"provider_call_count: {report.provider_call_count}",
        f"merge_strategy: {report.merge_strategy}",
        f"dry_run_only: {str(report.dry_run_only).lower()}",
        f"promotion_attempted: {str(report.promotion_attempted).lower()}",
        "",
        "## Assignments",
    ]
    for assignment in report.assignment_reports:
        lines.append(f"- {assignment.assignment_id}: {assignment.profile_id} ({assignment.status})")
    lines.extend(["", "## Reason codes", *[f"- {reason}" for reason in report.reason_codes], ""])
    return "\n".join(lines)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
