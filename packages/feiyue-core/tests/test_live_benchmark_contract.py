from __future__ import annotations

import pytest

from feiyue_core.evaluation.comparison import build_benchmark_strategy_comparison
from feiyue_core.evaluation.live_benchmark import (
    BenchmarkAuthorization,
    BenchmarkMode,
    BenchmarkRunStatus,
    StrategyRole,
    execute_benchmark_run,
    plan_benchmark_run,
)
from feiyue_core.evaluation.trace_fixture import default_strategy_trace_fixtures


def test_replay_fixtures_produce_same_comparison_metrics() -> None:
    fixtures = default_strategy_trace_fixtures()
    expected = build_benchmark_strategy_comparison("wave3-replay", fixtures)

    result = execute_benchmark_run(
        plan_benchmark_run(
            run_id="wave3-replay",
            mode=BenchmarkMode.REPLAY,
            strategy_roles=[role.value for role in StrategyRole],
            fixtures=fixtures,
        )
    )

    assert result.status == BenchmarkRunStatus.REPLAYED
    assert result.provider_call_count == 0
    assert result.comparison == expected
    assert result.reason_codes == ["provider_free_replay"]


def test_live_mode_without_authorization_is_blocked_fail_closed() -> None:
    plan = plan_benchmark_run(
        run_id="wave3-live-blocked",
        mode="live",
        strategy_roles=["weak-only", "strong-reference"],
        fixtures=default_strategy_trace_fixtures(),
    )

    assert plan.status == BenchmarkRunStatus.BLOCKED
    assert plan.comparison is None
    assert "missing_live_benchmark_authorization" in plan.reason_codes

    result = execute_benchmark_run(plan)
    assert result.status == BenchmarkRunStatus.BLOCKED
    assert result.provider_call_count == 0
    assert result.comparison is None


def test_live_mode_with_fake_authorization_produces_plan_but_no_network() -> None:
    authorization = BenchmarkAuthorization(
        authorization_id="auth.fake.wave3",
        authorized_by="test-suite",
        evidence_ids=["ticket:W3-3", "fixture:provider-free"],
        scopes=["live_benchmark_plan"],
    )

    plan = plan_benchmark_run(
        run_id="wave3-live-authorized-plan",
        mode=BenchmarkMode.LIVE,
        strategy_roles=[StrategyRole.WEAK_ONLY, StrategyRole.STRONG_REFERENCE],
        fixtures=default_strategy_trace_fixtures(),
        authorization=authorization,
    )

    assert plan.status == BenchmarkRunStatus.PLANNED
    assert plan.provider_call_count == 0
    assert plan.authorization == authorization
    assert plan.comparison is None
    assert plan.reason_codes == ["live_authorized_plan_only", "provider_execution_not_implemented"]

    result = execute_benchmark_run(plan)
    assert result.status == BenchmarkRunStatus.PLANNED
    assert result.provider_call_count == 0
    assert result.reason_codes == plan.reason_codes


def test_live_mode_authorization_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_ids"):
        BenchmarkAuthorization(
            authorization_id="auth.missing.evidence",
            authorized_by="test-suite",
            evidence_ids=[],
            scopes=["live_benchmark_plan"],
        )
