"""Plan-only live A/B smoke preparation.

This module prepares an auditable checklist for a future explicitly authorized
real Hermes profile multi-worker dry-run and optional teacher escalation smoke.
It is intentionally non-executing: it reads local approval records, validates
that they exactly apply, and writes only plan artifacts when requested.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from feiyue_core.schemas.common import FeiyueModel


class LiveSmokePlanStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class LiveSmokeAuthorization(FeiyueModel):
    """Exact local approval record for preparing a live A/B dry-run smoke."""

    authorization_id: str
    authorized_by: str
    plan_id: str
    run_id: str
    task_id: str
    approved_action: str = "prepare_live_ab_smoke_dry_run"
    worker_profile_id: str
    scopes: list[str]
    max_profile_calls: int = Field(default=1, ge=0)
    timeout_seconds: int = Field(default=120, ge=1)
    budget_ceiling: str
    dry_run_only: bool = True
    promotion_disabled: bool = True
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator(
        "authorization_id",
        "authorized_by",
        "plan_id",
        "run_id",
        "task_id",
        "approved_action",
        "worker_profile_id",
        "budget_ceiling",
        "reason",
    )
    @classmethod
    def _required_string(cls, value: str) -> str:
        return _non_empty(value, "authorization text field")

    @field_validator("scopes")
    @classmethod
    def _required_scopes(cls, value: list[str]) -> list[str]:
        return _non_empty_list(value, "authorization scopes")

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


class LiveSmokeTeacherEscalationAuthorization(FeiyueModel):
    """Separate exact approval for live-smoke teacher escalation preparation."""

    authorization_id: str
    authorized_by: str
    plan_id: str
    run_id: str
    task_id: str
    approved_action: str = "prepare_live_ab_teacher_escalation_dry_run"
    worker_profile_id: str
    teacher_profile_id: str
    scopes: list[str]
    max_profile_calls: int = Field(default=3, ge=0)
    timeout_seconds: int = Field(default=180, ge=1)
    budget_ceiling: str
    dry_run_only: bool = True
    promotion_disabled: bool = True
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    reason: str

    @field_validator(
        "authorization_id",
        "authorized_by",
        "plan_id",
        "run_id",
        "task_id",
        "approved_action",
        "worker_profile_id",
        "teacher_profile_id",
        "budget_ceiling",
        "reason",
    )
    @classmethod
    def _required_string(cls, value: str) -> str:
        return _non_empty(value, "teacher authorization text field")

    @field_validator("scopes")
    @classmethod
    def _required_scopes(cls, value: list[str]) -> list[str]:
        return _non_empty_list(value, "teacher authorization scopes")

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


class LiveSmokePlan(FeiyueModel):
    """Fail-closed plan/checklist for a future live A/B smoke."""

    plan_id: str
    run_id: str
    task_id: str
    status: LiveSmokePlanStatus
    ready: bool
    selected_worker_profile: str
    optional_teacher_profile: str | None = None
    teacher_escalation_enabled: bool = False
    authorization_id: str | None = None
    teacher_authorization_id: str | None = None
    required_approval_paths: list[str]
    required_evidence_paths: list[str]
    expected_verifier_command: str
    max_profile_calls: int = Field(default=1, ge=0)
    timeout_seconds: int = Field(default=120, ge=1)
    budget_ceiling: str = "0.01 USD"
    dry_run_only: bool = True
    promotion_disabled: bool = True
    provider_call_count: int = Field(default=0, ge=0)
    global_hermes_config_mutated: bool = False
    production_side_effects_enabled: bool = False
    reason_codes: list[str]
    checklist: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("plan_id", "run_id", "task_id", "selected_worker_profile", "expected_verifier_command", "budget_ceiling")
    @classmethod
    def _required_string(cls, value: str) -> str:
        return _non_empty(value, "plan text field")

    @field_validator("required_approval_paths", "required_evidence_paths", "reason_codes")
    @classmethod
    def _required_string_list(cls, value: list[str]) -> list[str]:
        return _non_empty_list(value, "plan list field")


def live_smoke_dir(project_root: str | Path, plan_id: str) -> Path:
    return Path(project_root) / ".hermes" / "live-smoke-plans" / plan_id


def live_smoke_plan_path(project_root: str | Path, plan_id: str) -> Path:
    return live_smoke_dir(project_root, plan_id) / "plan.json"


def live_smoke_approval_path(project_root: str | Path, plan_id: str) -> Path:
    return live_smoke_dir(project_root, plan_id) / "approval.json"


def live_smoke_teacher_approval_path(project_root: str | Path, plan_id: str) -> Path:
    return live_smoke_dir(project_root, plan_id) / "teacher-approval.json"


def live_smoke_evidence_path(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root) / ".hermes" / "live-smokes" / run_id / "evidence.json"


def build_live_smoke_plan(
    *,
    project_root: str | Path,
    plan_id: str,
    run_id: str,
    task_id: str,
    worker_profile_id: str,
    expected_verifier_command: str,
    teacher_profile_id: str | None = None,
    teacher_escalation_enabled: bool = False,
    max_profile_calls: int = 1,
    timeout_seconds: int = 120,
    budget_ceiling: str = "0.01 USD",
    approval_path: str | Path | None = None,
    teacher_approval_path: str | Path | None = None,
) -> LiveSmokePlan:
    """Build a non-executing live-smoke preparation plan.

    Approval files are read and validated if present. Missing or mismatched
    approval evidence blocks readiness; this function never starts Hermes,
    contacts providers, promotes code, or mutates global Hermes configuration.
    """

    root = Path(project_root)
    approval_file = Path(approval_path) if approval_path is not None else live_smoke_approval_path(root, plan_id)
    teacher_file = (
        Path(teacher_approval_path) if teacher_approval_path is not None else live_smoke_teacher_approval_path(root, plan_id)
    )
    required_approvals = [str(approval_file)]
    if teacher_escalation_enabled:
        required_approvals.append(str(teacher_file))

    reason_codes: list[str] = []
    authorization_id: str | None = None
    teacher_authorization_id: str | None = None

    authorization, authorization_read_reasons = _read_authorization(approval_file)
    reason_codes.extend(authorization_read_reasons)
    if authorization is None:
        if not authorization_read_reasons:
            reason_codes.append("missing_live_smoke_approval")
    else:
        authorization_id = authorization.authorization_id
        reason_codes.extend(
            _authorization_reasons(
                authorization=authorization,
                plan_id=plan_id,
                run_id=run_id,
                task_id=task_id,
                worker_profile_id=worker_profile_id,
                max_profile_calls=max_profile_calls,
                timeout_seconds=timeout_seconds,
                budget_ceiling=budget_ceiling,
            )
        )

    if teacher_escalation_enabled:
        if not teacher_profile_id:
            reason_codes.append("teacher_profile_required_when_escalation_enabled")
        teacher_authorization, teacher_read_reasons = _read_teacher_authorization(teacher_file)
        reason_codes.extend(teacher_read_reasons)
        if teacher_authorization is None:
            if not teacher_read_reasons:
                reason_codes.append("missing_live_smoke_teacher_escalation_approval")
        else:
            teacher_authorization_id = teacher_authorization.authorization_id
            reason_codes.extend(
                _teacher_authorization_reasons(
                    authorization=teacher_authorization,
                    plan_id=plan_id,
                    run_id=run_id,
                    task_id=task_id,
                    worker_profile_id=worker_profile_id,
                    teacher_profile_id=teacher_profile_id,
                    max_profile_calls=max(3, max_profile_calls),
                    timeout_seconds=timeout_seconds,
                )
            )

    if not reason_codes:
        reason_codes = ["live_smoke_approval_applies"]
        if teacher_escalation_enabled:
            reason_codes.append("live_smoke_teacher_escalation_approval_applies")
        reason_codes.append("plan_only_no_live_calls")

    ready = reason_codes[-1:] == ["plan_only_no_live_calls"]
    status = LiveSmokePlanStatus.READY if ready else LiveSmokePlanStatus.BLOCKED
    return LiveSmokePlan(
        plan_id=plan_id,
        run_id=run_id,
        task_id=task_id,
        status=status,
        ready=ready,
        selected_worker_profile=worker_profile_id,
        optional_teacher_profile=teacher_profile_id,
        teacher_escalation_enabled=teacher_escalation_enabled,
        authorization_id=authorization_id,
        teacher_authorization_id=teacher_authorization_id,
        required_approval_paths=required_approvals,
        required_evidence_paths=[str(live_smoke_evidence_path(root, run_id))],
        expected_verifier_command=expected_verifier_command,
        max_profile_calls=max_profile_calls,
        timeout_seconds=timeout_seconds,
        budget_ceiling=budget_ceiling,
        dry_run_only=True,
        promotion_disabled=True,
        provider_call_count=0,
        global_hermes_config_mutated=False,
        production_side_effects_enabled=False,
        reason_codes=_dedupe(reason_codes),
        checklist=_checklist(teacher_escalation_enabled=teacher_escalation_enabled),
        metadata={"lane": "batch1-live-ab-smoke-prep", "mode": "plan-only"},
    )


def write_live_smoke_plan(
    *,
    project_root: str | Path,
    plan_id: str,
    run_id: str,
    task_id: str,
    worker_profile_id: str,
    expected_verifier_command: str,
    teacher_profile_id: str | None = None,
    teacher_escalation_enabled: bool = False,
    max_profile_calls: int = 1,
    timeout_seconds: int = 120,
    budget_ceiling: str = "0.01 USD",
    approval_path: str | Path | None = None,
    teacher_approval_path: str | Path | None = None,
) -> LiveSmokePlan:
    plan = build_live_smoke_plan(
        project_root=project_root,
        plan_id=plan_id,
        run_id=run_id,
        task_id=task_id,
        worker_profile_id=worker_profile_id,
        expected_verifier_command=expected_verifier_command,
        teacher_profile_id=teacher_profile_id,
        teacher_escalation_enabled=teacher_escalation_enabled,
        max_profile_calls=max_profile_calls,
        timeout_seconds=timeout_seconds,
        budget_ceiling=budget_ceiling,
        approval_path=approval_path,
        teacher_approval_path=teacher_approval_path,
    )
    root = Path(project_root)
    plan_dir = live_smoke_dir(root, plan.plan_id)
    plan_dir.mkdir(parents=True, exist_ok=True)
    live_smoke_plan_path(root, plan.plan_id).write_text(
        json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "plan.md").write_text(_render_markdown(plan), encoding="utf-8")
    return plan


def _read_authorization(path: Path) -> tuple[LiveSmokeAuthorization | None, list[str]]:
    if not path.exists():
        return None, []
    try:
        return LiveSmokeAuthorization.model_validate_json(path.read_text(encoding="utf-8")), []
    except Exception:
        return None, ["invalid_live_smoke_approval"]


def _read_teacher_authorization(path: Path) -> tuple[LiveSmokeTeacherEscalationAuthorization | None, list[str]]:
    if not path.exists():
        return None, []
    try:
        return LiveSmokeTeacherEscalationAuthorization.model_validate_json(path.read_text(encoding="utf-8")), []
    except Exception:
        return None, ["invalid_live_smoke_teacher_escalation_approval"]


def _authorization_reasons(
    *,
    authorization: LiveSmokeAuthorization,
    plan_id: str,
    run_id: str,
    task_id: str,
    worker_profile_id: str,
    max_profile_calls: int,
    timeout_seconds: int,
    budget_ceiling: str,
) -> list[str]:
    reasons: list[str] = []
    if authorization.plan_id != plan_id:
        reasons.append("approval_plan_id_mismatch")
    if authorization.run_id != run_id:
        reasons.append("approval_run_id_mismatch")
    if authorization.task_id != task_id:
        reasons.append("approval_task_id_mismatch")
    if authorization.approved_action != "prepare_live_ab_smoke_dry_run":
        reasons.append("approval_action_mismatch")
    if authorization.worker_profile_id != worker_profile_id:
        reasons.append("approval_worker_profile_mismatch")
    if not authorization.allows("live_smoke_prepare"):
        reasons.append("approval_scope_live_smoke_prepare_missing")
    if not authorization.dry_run_only:
        reasons.append("approval_must_be_dry_run_only")
    if not authorization.promotion_disabled:
        reasons.append("approval_must_disable_promotion")
    if authorization.max_profile_calls < max_profile_calls:
        reasons.append("approval_max_profile_calls_too_low")
    if authorization.timeout_seconds < timeout_seconds:
        reasons.append("approval_timeout_seconds_too_low")
    if authorization.budget_ceiling != budget_ceiling:
        reasons.append("approval_budget_ceiling_mismatch")
    return reasons


def _teacher_authorization_reasons(
    *,
    authorization: LiveSmokeTeacherEscalationAuthorization,
    plan_id: str,
    run_id: str,
    task_id: str,
    worker_profile_id: str,
    teacher_profile_id: str | None,
    max_profile_calls: int,
    timeout_seconds: int,
) -> list[str]:
    reasons: list[str] = []
    if authorization.plan_id != plan_id:
        reasons.append("teacher_approval_plan_id_mismatch")
    if authorization.run_id != run_id:
        reasons.append("teacher_approval_run_id_mismatch")
    if authorization.task_id != task_id:
        reasons.append("teacher_approval_task_id_mismatch")
    if authorization.approved_action != "prepare_live_ab_teacher_escalation_dry_run":
        reasons.append("teacher_approval_action_mismatch")
    if authorization.worker_profile_id != worker_profile_id:
        reasons.append("teacher_approval_worker_profile_mismatch")
    if authorization.teacher_profile_id != teacher_profile_id:
        reasons.append("teacher_approval_teacher_profile_mismatch")
    if not authorization.allows("live_smoke_teacher_escalation"):
        reasons.append("teacher_approval_scope_missing")
    if not authorization.dry_run_only:
        reasons.append("teacher_approval_must_be_dry_run_only")
    if not authorization.promotion_disabled:
        reasons.append("teacher_approval_must_disable_promotion")
    if authorization.max_profile_calls < max_profile_calls:
        reasons.append("teacher_approval_max_profile_calls_too_low")
    if authorization.timeout_seconds < timeout_seconds:
        reasons.append("teacher_approval_timeout_seconds_too_low")
    return reasons


def _checklist(*, teacher_escalation_enabled: bool) -> list[str]:
    items = [
        "Confirm selected worker profile matches approval exactly.",
        "Confirm dry_run_only remains true and promotion remains disabled.",
        "Confirm expected verifier command is the only planned verification command.",
        "Confirm required approval files are retained with the run evidence.",
        "Do not start Hermes profiles, providers, GitHub API calls, PR creation, or promotion from this plan.",
    ]
    if teacher_escalation_enabled:
        items.append("Confirm separate teacher escalation authorization before any teacher retry smoke.")
    return items


def _render_markdown(plan: LiveSmokePlan) -> str:
    return "\n".join(
        [
            f"# Live A/B smoke plan: {plan.plan_id}",
            "",
            f"status: {plan.status}",
            f"ready: {str(plan.ready).lower()}",
            f"run_id: {plan.run_id}",
            f"task_id: {plan.task_id}",
            f"selected_worker_profile: {plan.selected_worker_profile}",
            f"optional_teacher_profile: {plan.optional_teacher_profile or 'none'}",
            f"dry_run_only: {str(plan.dry_run_only).lower()}",
            f"promotion_disabled: {str(plan.promotion_disabled).lower()}",
            f"global_hermes_config_mutated: {str(plan.global_hermes_config_mutated).lower()}",
            f"production_side_effects_enabled: {str(plan.production_side_effects_enabled).lower()}",
            f"expected_verifier_command: `{plan.expected_verifier_command}`",
            "",
            "## Required approvals",
            *[f"- {path}" for path in plan.required_approval_paths],
            "",
            "## Required evidence",
            *[f"- {path}" for path in plan.required_evidence_paths],
            "",
            "## Checklist",
            *[f"- {item}" for item in plan.checklist],
            "",
            "## Reason codes",
            *[f"- {reason}" for reason in plan.reason_codes],
            "",
        ]
    )


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _non_empty_list(value: list[str], field_name: str) -> list[str]:
    normalized = [str(item).strip() for item in value]
    if not normalized or any(not item for item in normalized):
        raise ValueError(f"{field_name} must contain non-empty strings")
    return normalized


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
