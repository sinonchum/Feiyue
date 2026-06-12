import pytest

from feiyue_core.safety import (
    GovernanceAction,
    HumanApprovalRecord,
    PolicyConfigLoadError,
    PolicyDecisionReason,
    PolicyGovernor,
    PolicyGovernorConfig,
    PolicyGovernorConfigLoader,
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


def test_policy_governor_allows_high_risk_operation_with_matching_human_approval() -> None:
    request = PolicyRequest(
        task_id="m12-approved-risk",
        operation="promotion",
        risk_level=RiskLevel.HIGH,
        worker_retries_used=0,
        teacher_calls_used=0,
        estimated_tokens=300,
        contains_sensitive_data=False,
    )
    approval = HumanApprovalRecord(
        approval_id="approval-003",
        task_id="m12-approved-risk",
        approved_action="promotion",
        approver="Simon",
        approved_at="2026-06-13T10:00:00Z",
        reason="Approve high-risk promotion after review.",
    )

    decision = PolicyGovernor().evaluate(request, approval_record=approval)

    assert decision.action == GovernanceAction.ALLOW
    assert decision.reason == PolicyDecisionReason.WITHIN_POLICY
    assert decision.requires_human_approval is False
    assert decision.audit_metadata["human_approval_id"] == "approval-003"


def test_policy_governor_rejects_non_matching_human_approval() -> None:
    request = PolicyRequest(
        task_id="m12-approval-match",
        operation="promotion",
        risk_level=RiskLevel.HIGH,
        worker_retries_used=0,
        teacher_calls_used=0,
        estimated_tokens=300,
        contains_sensitive_data=False,
    )
    approval = HumanApprovalRecord(
        approval_id="approval-004",
        task_id="m12-approval-match",
        approved_action="provider_call",
        approver="Simon",
        approved_at="2026-06-13T10:00:00Z",
        reason="Approve a different action only.",
    )

    decision = PolicyGovernor().evaluate(request, approval_record=approval)

    assert decision.action == GovernanceAction.ESCALATE
    assert decision.reason == PolicyDecisionReason.HIGH_RISK_OPERATION
    assert decision.requires_human_approval is True
    assert decision.audit_metadata["human_approval_id"] is None


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
        "human_approval_id": None,
    }


def test_policy_config_loader_uses_safe_defaults_when_yaml_missing(tmp_path) -> None:
    config = PolicyGovernorConfigLoader(tmp_path).load()

    assert config == PolicyGovernorConfig()


def test_policy_config_loader_reads_project_yaml(tmp_path) -> None:
    config_dir = tmp_path / ".feiyue"
    config_dir.mkdir()
    (config_dir / "policy.yaml").write_text(
        "\n".join(
            [
                "max_worker_retries: 1",
                "max_teacher_calls: 0",
                "max_tokens_per_task: 1200",
                "require_human_for_high_risk: false",
                "require_privacy_approval_for_sensitive_data: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = PolicyGovernorConfigLoader(tmp_path).load()

    assert config.max_worker_retries == 1
    assert config.max_teacher_calls == 0
    assert config.max_tokens_per_task == 1200
    assert config.require_human_for_high_risk is False
    assert config.require_privacy_approval_for_sensitive_data is True


def test_policy_config_loader_rejects_invalid_yaml_value_with_typed_error(tmp_path) -> None:
    config_dir = tmp_path / ".feiyue"
    config_dir.mkdir()
    policy_path = config_dir / "policy.yaml"
    policy_path.write_text("max_worker_retries: nope\n", encoding="utf-8")

    with pytest.raises(PolicyConfigLoadError) as exc_info:
        PolicyGovernorConfigLoader(tmp_path).load()

    assert exc_info.value.path == policy_path
    assert "max_worker_retries" in str(exc_info.value)


def test_human_approval_record_allows_exact_pending_action() -> None:
    request = PolicyRequest(
        task_id="m12-approval",
        operation="promotion",
        risk_level=RiskLevel.HIGH,
        worker_retries_used=0,
        teacher_calls_used=0,
        estimated_tokens=300,
        contains_sensitive_data=False,
    )
    approval = HumanApprovalRecord(
        approval_id="approval-001",
        task_id="m12-approval",
        approved_action="promotion",
        approver="Simon",
        approved_at="2026-06-13T10:00:00Z",
        reason="Approve controlled test promotion.",
    )

    assert approval.applies_to(request) is True
    assert approval.model_dump(mode="json") == {
        "approval_id": "approval-001",
        "task_id": "m12-approval",
        "approved_action": "promotion",
        "approver": "Simon",
        "approved_at": "2026-06-13T10:00:00Z",
        "reason": "Approve controlled test promotion.",
    }


def test_human_approval_record_does_not_apply_to_other_task_or_action() -> None:
    approval = HumanApprovalRecord(
        approval_id="approval-002",
        task_id="m12-approval",
        approved_action="promotion",
        approver="Simon",
        approved_at="2026-06-13T10:00:00Z",
        reason="Approve only promotion for this task.",
    )

    other_task_request = PolicyRequest(
        task_id="m12-other",
        operation="promotion",
        risk_level=RiskLevel.HIGH,
        worker_retries_used=0,
        teacher_calls_used=0,
        estimated_tokens=300,
        contains_sensitive_data=False,
    )
    other_action_request = PolicyRequest(
        task_id="m12-approval",
        operation="provider_call",
        risk_level=RiskLevel.HIGH,
        worker_retries_used=0,
        teacher_calls_used=0,
        estimated_tokens=300,
        contains_sensitive_data=False,
    )

    assert approval.applies_to(other_task_request) is False
    assert approval.applies_to(other_action_request) is False
