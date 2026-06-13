"""Gated weak/strong live benchmark contracts.

This module is intentionally provider-free. Replay mode consumes deterministic
``BenchmarkTraceFixture`` inputs; live mode fails closed unless an explicit
authorization record is present and, even then, only produces an auditable plan.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from feiyue_core.evaluation.comparison import BenchmarkStrategyComparison, build_benchmark_strategy_comparison
from feiyue_core.evaluation.trace_fixture import BenchmarkTraceFixture
from feiyue_core.schemas.common import FeiyueModel


class StrategyRole(StrEnum):
    WEAK_ONLY = "weak-only"
    WEAK_TASK_CONTRACT = "weak+task-contract"
    WEAK_VERIFIER = "weak+verifier"
    WEAK_SPARSE_TEACHER = "weak+sparse-teacher"
    STRONG_REFERENCE = "strong-reference"


class BenchmarkMode(StrEnum):
    REPLAY = "replay"
    LIVE = "live"


class BenchmarkRunStatus(StrEnum):
    PLANNED = "planned"
    REPLAYED = "replayed"
    BLOCKED = "blocked"


class BenchmarkAuthorization(FeiyueModel):
    """Minimal local authorization/evidence record for gated live planning."""

    authorization_id: str
    authorized_by: str
    evidence_ids: list[str]
    scopes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("authorization_id", "authorized_by")
    @classmethod
    def _required_string(cls, value: str) -> str:
        return _non_empty(value, "authorization field")

    @field_validator("evidence_ids", "scopes")
    @classmethod
    def _required_string_list(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("evidence_ids and scopes must be non-empty")
        return [_non_empty(item, "authorization list item") for item in value]

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes)


class BenchmarkRunPlan(FeiyueModel):
    """Auditable run plan/result envelope for replay or gated live benchmarking."""

    run_id: str
    mode: BenchmarkMode
    strategy_roles: list[StrategyRole]
    status: BenchmarkRunStatus
    reason_codes: list[str]
    fixture_count: int = Field(ge=0)
    provider_call_count: int = Field(default=0, ge=0)
    authorization: BenchmarkAuthorization | None = None
    comparison: BenchmarkStrategyComparison | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _non_empty(value, "run_id")

    @field_validator("strategy_roles")
    @classmethod
    def _validate_strategy_roles(cls, value: list[StrategyRole]) -> list[StrategyRole]:
        if not value:
            raise ValueError("strategy_roles must be non-empty")
        return value

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("reason_codes must be non-empty")
        return [_non_empty(item, "reason_code") for item in value]


BenchmarkRunResult = BenchmarkRunPlan


def plan_benchmark_run(
    *,
    run_id: str,
    mode: BenchmarkMode | str,
    strategy_roles: list[StrategyRole | str],
    fixtures: list[BenchmarkTraceFixture] | None = None,
    authorization: BenchmarkAuthorization | None = None,
) -> BenchmarkRunPlan:
    """Build a provider-free benchmark plan.

    Replay mode immediately attaches deterministic comparison metrics. Live mode
    is fail-closed without authorization and never executes provider calls.
    """

    normalized_mode = BenchmarkMode(mode)
    normalized_roles = [StrategyRole(role) for role in strategy_roles]
    fixture_list = list(fixtures or [])

    if normalized_mode == BenchmarkMode.REPLAY:
        selected_fixtures = _select_fixtures(fixture_list, normalized_roles)
        comparison = build_benchmark_strategy_comparison(run_id, selected_fixtures)
        return BenchmarkRunPlan(
            run_id=run_id,
            mode=normalized_mode,
            strategy_roles=normalized_roles,
            status=BenchmarkRunStatus.REPLAYED,
            reason_codes=["provider_free_replay"],
            fixture_count=len(selected_fixtures),
            provider_call_count=0,
            authorization=authorization,
            comparison=comparison,
        )

    if authorization is None or not authorization.allows("live_benchmark_plan"):
        reason_codes = ["missing_live_benchmark_authorization"]
        if authorization is not None:
            reason_codes.append("authorization_scope_live_benchmark_plan_missing")
        return BenchmarkRunPlan(
            run_id=run_id,
            mode=normalized_mode,
            strategy_roles=normalized_roles,
            status=BenchmarkRunStatus.BLOCKED,
            reason_codes=reason_codes,
            fixture_count=len(fixture_list),
            provider_call_count=0,
            authorization=authorization,
            comparison=None,
        )

    return BenchmarkRunPlan(
        run_id=run_id,
        mode=normalized_mode,
        strategy_roles=normalized_roles,
        status=BenchmarkRunStatus.PLANNED,
        reason_codes=["live_authorized_plan_only", "provider_execution_not_implemented"],
        fixture_count=len(fixture_list),
        provider_call_count=0,
        authorization=authorization,
        comparison=None,
    )


def execute_benchmark_run(plan: BenchmarkRunPlan) -> BenchmarkRunResult:
    """Return the already materialized provider-free plan/result.

    The execution function is deliberately side-effect-free: replay results are
    already computed by ``plan_benchmark_run`` and live plans are not provider
    executable on this lane.
    """

    return plan


def _select_fixtures(fixtures: list[BenchmarkTraceFixture], roles: list[StrategyRole]) -> list[BenchmarkTraceFixture]:
    requested = {role.value for role in roles}
    selected = [fixture for fixture in fixtures if fixture.strategy_id in requested]
    missing = requested.difference(fixture.strategy_id for fixture in selected)
    if missing:
        raise ValueError(f"missing fixtures for strategy roles: {', '.join(sorted(missing))}")
    return selected


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized
