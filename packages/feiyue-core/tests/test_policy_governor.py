from feiyue_core.safety import (
    GovernanceAction,
    PolicyDecisionReason,
    PolicyGovernor,
    PolicyGovernorConfig,
    PolicyRequest,
    RiskLevel,
)


def test_policy_governor_allows_low_risk_within_budgets() -> None:
    decision = PolicyGovernor().evaluate(
        PolicyRequest(
            task_id="m12-allow",
            operation="worker_retry",
            risk_level=RiskLevel.LOW,
            worker_retries_used=1,
            teacher_calls_used=0,
            estimated_tokens=1200,
            contains_sensitive_data=False,
        )
    )

    assert decision.action == GovernanceAction.ALLOW
    assert decision.reason == PolicyDecisionReason.WITHIN_POLICY
    assert decision.requires_human_approval is False
    assert decision.audit_metadata["task_id"] == "m12-allow"
    assert decision.audit_metadata["risk_level"] == "low"


def test_policy_governor_escalates_high_risk_operations_before_execution() -> None:
    decision = PolicyGovernor().evaluate(
        PolicyRequest(
            task_id="m12-risk",
            operation="promotion",
            risk_level=RiskLevel.HIGH,
            worker_retries_used=0,
            teacher_calls_used=0,
            estimated_tokens=500,
            contains_sensitive_data=False,
        )
    )

    assert decision.action == GovernanceAction.ESCALATE
    assert decision.reason == PolicyDecisionReason.HIGH_RISK_OPERATION
    assert decision.requires_human_approval is True
    assert "manual approval" in decision.message


def test_policy_governor_blocks_worker_retry_budget_exhaustion() -> None:
    decision = PolicyGovernor(
        PolicyGovernorConfig(max_worker_retries=2, max_teacher_calls=1, max_tokens_per_task=4000)
    ).evaluate(
        PolicyRequest(
            task_id="m12-retry-budget",
            operation="worker_retry",
            risk_level=RiskLevel.MEDIUM,
            worker_retries_used=2,
            teacher_calls_used=0,
            estimated_tokens=600,
            contains_sensitive_data=False,
        )
    )

    assert decision.action == GovernanceAction.BLOCK
    assert decision.reason == PolicyDecisionReason.WORKER_RETRY_BUDGET_EXHAUSTED
    assert decision.requires_human_approval is False


def test_policy_governor_blocks_teacher_call_budget_exhaustion() -> None:
    decision = PolicyGovernor(
        PolicyGovernorConfig(max_worker_retries=3, max_teacher_calls=1, max_tokens_per_task=4000)
    ).evaluate(
        PolicyRequest(
            task_id="m12-teacher-budget",
            operation="teacher_call",
            risk_level=RiskLevel.MEDIUM,
            worker_retries_used=1,
            teacher_calls_used=1,
            estimated_tokens=800,
            contains_sensitive_data=False,
        )
    )

    assert decision.action == GovernanceAction.BLOCK
    assert decision.reason == PolicyDecisionReason.TEACHER_CALL_BUDGET_EXHAUSTED


def test_policy_governor_blocks_token_budget_exhaustion() -> None:
    decision = PolicyGovernor(PolicyGovernorConfig(max_tokens_per_task=1000)).evaluate(
        PolicyRequest(
            task_id="m12-token-budget",
            operation="candidate_generation",
            risk_level=RiskLevel.LOW,
            worker_retries_used=0,
            teacher_calls_used=0,
            estimated_tokens=1001,
            contains_sensitive_data=False,
        )
    )

    assert decision.action == GovernanceAction.BLOCK
    assert decision.reason == PolicyDecisionReason.TOKEN_BUDGET_EXCEEDED


def test_policy_governor_escalates_sensitive_data_unless_privacy_approved() -> None:
    decision = PolicyGovernor().evaluate(
        PolicyRequest(
            task_id="m12-privacy",
            operation="provider_call",
            risk_level=RiskLevel.LOW,
            worker_retries_used=0,
            teacher_calls_used=0,
            estimated_tokens=700,
            contains_sensitive_data=True,
            privacy_approved=False,
        )
    )

    assert decision.action == GovernanceAction.ESCALATE
    assert decision.reason == PolicyDecisionReason.PRIVACY_APPROVAL_REQUIRED
    assert decision.requires_human_approval is True


def test_policy_governor_serializes_deterministic_decision() -> None:
    decision = PolicyGovernor().evaluate(
        PolicyRequest(
            task_id="m12-json",
            operation="worker_retry",
            risk_level=RiskLevel.LOW,
            worker_retries_used=0,
            teacher_calls_used=0,
            estimated_tokens=250,
            contains_sensitive_data=False,
        )
    )

    dumped = decision.model_dump(mode="json")
    assert dumped["action"] == "allow"
    assert dumped["reason"] == "within_policy"
    assert dumped["audit_metadata"] == {
        "task_id": "m12-json",
        "operation": "worker_retry",
        "risk_level": "low",
        "worker_retries_used": 0,
        "teacher_calls_used": 0,
        "estimated_tokens": 250,
        "contains_sensitive_data": False,
        "privacy_approved": False,
    }
