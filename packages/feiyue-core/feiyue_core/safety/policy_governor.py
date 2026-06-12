from __future__ import annotations

from enum import StrEnum

from pydantic import Field

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

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if request.estimated_tokens > self.config.max_tokens_per_task:
            return self._decision(
                request,
                action=GovernanceAction.BLOCK,
                reason=PolicyDecisionReason.TOKEN_BUDGET_EXCEEDED,
                message=f"estimated tokens {request.estimated_tokens} exceed task budget {self.config.max_tokens_per_task}",
            )

        if request.operation == "worker_retry" and request.worker_retries_used >= self.config.max_worker_retries:
            return self._decision(
                request,
                action=GovernanceAction.BLOCK,
                reason=PolicyDecisionReason.WORKER_RETRY_BUDGET_EXHAUSTED,
                message="worker retry budget exhausted",
            )

        if request.operation == "teacher_call" and request.teacher_calls_used >= self.config.max_teacher_calls:
            return self._decision(
                request,
                action=GovernanceAction.BLOCK,
                reason=PolicyDecisionReason.TEACHER_CALL_BUDGET_EXHAUSTED,
                message="teacher call budget exhausted",
            )

        if (
            request.contains_sensitive_data
            and self.config.require_privacy_approval_for_sensitive_data
            and not request.privacy_approved
        ):
            return self._decision(
                request,
                action=GovernanceAction.ESCALATE,
                reason=PolicyDecisionReason.PRIVACY_APPROVAL_REQUIRED,
                message="sensitive data requires privacy approval before provider execution",
                requires_human_approval=True,
            )

        if request.risk_level == RiskLevel.HIGH and self.config.require_human_for_high_risk:
            return self._decision(
                request,
                action=GovernanceAction.ESCALATE,
                reason=PolicyDecisionReason.HIGH_RISK_OPERATION,
                message="high-risk operation requires manual approval before execution",
                requires_human_approval=True,
            )

        return self._decision(
            request,
            action=GovernanceAction.ALLOW,
            reason=PolicyDecisionReason.WITHIN_POLICY,
            message="request is within policy",
        )

    @staticmethod
    def _decision(
        request: PolicyRequest,
        *,
        action: GovernanceAction,
        reason: PolicyDecisionReason,
        message: str,
        requires_human_approval: bool = False,
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
            },
        )
