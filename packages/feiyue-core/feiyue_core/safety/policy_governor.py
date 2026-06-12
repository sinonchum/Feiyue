from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from feiyue_core.schemas.common import FeiyueModel


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GovernanceAction(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


class PolicyDecisionReason(StrEnum):
    WITHIN_POLICY = "within_policy"
    HIGH_RISK_OPERATION = "high_risk_operation"
    WORKER_RETRY_BUDGET_EXHAUSTED = "worker_retry_budget_exhausted"
    TEACHER_CALL_BUDGET_EXHAUSTED = "teacher_call_budget_exhausted"
    TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"
    PRIVACY_APPROVAL_REQUIRED = "privacy_approval_required"


class PolicyGovernorConfig(FeiyueModel):
    max_worker_retries: int = Field(default=3, ge=0)
    max_teacher_calls: int = Field(default=2, ge=0)
    max_tokens_per_task: int = Field(default=8000, ge=0)
    require_human_for_high_risk: bool = True
    require_privacy_approval_for_sensitive_data: bool = True


class PolicyConfigLoadError(ValueError):
    """Raised when a project policy config cannot be parsed or validated."""

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(f"invalid policy config at {path}: {message}")


class PolicyGovernorConfigLoader:
    """Load provider-free safety policy from .feiyue/policy.yaml with safe defaults."""

    def __init__(self, project_root: str | Path, relative_path: str = ".feiyue/policy.yaml") -> None:
        self.project_root = Path(project_root)
        self.relative_path = relative_path

    @property
    def path(self) -> Path:
        return self.project_root / self.relative_path

    def load(self) -> PolicyGovernorConfig:
        if not self.path.exists():
            return PolicyGovernorConfig()

        try:
            data = self._parse_simple_yaml(self.path.read_text(encoding="utf-8"))
            return PolicyGovernorConfig.model_validate(data)
        except (PolicyConfigLoadError, ValidationError) as exc:
            if isinstance(exc, PolicyConfigLoadError):
                raise
            raise PolicyConfigLoadError(self.path, str(exc)) from exc

    def _parse_simple_yaml(self, text: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise PolicyConfigLoadError(self.path, f"line {line_number} is not a key-value pair")
            key, raw_value = line.split(":", 1)
            key = key.strip()
            value = raw_value.strip()
            if not key:
                raise PolicyConfigLoadError(self.path, f"line {line_number} has an empty key")
            data[key] = self._parse_scalar(value)
        return data

    @staticmethod
    def _parse_scalar(value: str) -> Any:
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if value.isdecimal():
            return int(value)
        return value


class HumanApprovalRecord(FeiyueModel):
    approval_id: str
    task_id: str
    approved_action: str
    approver: str
    approved_at: str
    reason: str

    def applies_to(self, request: "PolicyRequest") -> bool:
        return self.task_id == request.task_id and self.approved_action == request.operation


class PolicyRequest(FeiyueModel):
    task_id: str
    operation: str
    risk_level: RiskLevel
    worker_retries_used: int = Field(ge=0)
    teacher_calls_used: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    contains_sensitive_data: bool
    privacy_approved: bool = False


class PolicyDecision(FeiyueModel):
    action: GovernanceAction
    reason: PolicyDecisionReason
    message: str
    requires_human_approval: bool = False
    audit_metadata: dict[str, object] = Field(default_factory=dict)


class PolicyGovernor:
    """Provider-free policy gate for M12 safety, budget, and privacy controls."""

    def __init__(self, config: PolicyGovernorConfig | None = None) -> None:
        self.config = config or PolicyGovernorConfig()

    def evaluate(self, request: PolicyRequest, approval_record: HumanApprovalRecord | None = None) -> PolicyDecision:
        approval_applies = approval_record is not None and approval_record.applies_to(request)
        approval_id = approval_record.approval_id if approval_record is not None and approval_applies else None
        if request.estimated_tokens > self.config.max_tokens_per_task:
            return self._decision(
                request,
                action=GovernanceAction.BLOCK,
                reason=PolicyDecisionReason.TOKEN_BUDGET_EXCEEDED,
                message=f"estimated tokens {request.estimated_tokens} exceed task budget {self.config.max_tokens_per_task}",
                human_approval_id=approval_id,
            )

        if request.operation == "worker_retry" and request.worker_retries_used >= self.config.max_worker_retries:
            return self._decision(
                request,
                action=GovernanceAction.BLOCK,
                reason=PolicyDecisionReason.WORKER_RETRY_BUDGET_EXHAUSTED,
                message="worker retry budget exhausted",
                human_approval_id=approval_id,
            )

        if request.operation == "teacher_call" and request.teacher_calls_used >= self.config.max_teacher_calls:
            return self._decision(
                request,
                action=GovernanceAction.BLOCK,
                reason=PolicyDecisionReason.TEACHER_CALL_BUDGET_EXHAUSTED,
                message="teacher call budget exhausted",
                human_approval_id=approval_id,
            )

        if (
            request.contains_sensitive_data
            and self.config.require_privacy_approval_for_sensitive_data
            and not request.privacy_approved
            and not approval_applies
        ):
            return self._decision(
                request,
                action=GovernanceAction.ESCALATE,
                reason=PolicyDecisionReason.PRIVACY_APPROVAL_REQUIRED,
                message="sensitive data requires privacy approval before provider execution",
                requires_human_approval=True,
                human_approval_id=approval_id,
            )

        if request.risk_level == RiskLevel.HIGH and self.config.require_human_for_high_risk and not approval_applies:
            return self._decision(
                request,
                action=GovernanceAction.ESCALATE,
                reason=PolicyDecisionReason.HIGH_RISK_OPERATION,
                message="high-risk operation requires manual approval before execution",
                requires_human_approval=True,
                human_approval_id=approval_id,
            )

        return self._decision(
            request,
            action=GovernanceAction.ALLOW,
            reason=PolicyDecisionReason.WITHIN_POLICY,
            message="request is within policy",
            human_approval_id=approval_id,
        )

    @staticmethod
    def _decision(
        request: PolicyRequest,
        *,
        action: GovernanceAction,
        reason: PolicyDecisionReason,
        message: str,
        requires_human_approval: bool = False,
        human_approval_id: str | None = None,
    ) -> PolicyDecision:
        return PolicyDecision(
            action=action,
            reason=reason,
            message=message,
            requires_human_approval=requires_human_approval,
            audit_metadata={
                "task_id": request.task_id,
                "operation": request.operation,
                "risk_level": request.risk_level.value,
                "worker_retries_used": request.worker_retries_used,
                "teacher_calls_used": request.teacher_calls_used,
                "estimated_tokens": request.estimated_tokens,
                "contains_sensitive_data": request.contains_sensitive_data,
                "privacy_approved": request.privacy_approved,
                "human_approval_id": human_approval_id,
            },
        )
