"""Strategy comparison reports for Feiyue evaluation scorecards."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field, field_validator

from feiyue_core.evaluation.scorecard import StrategyScorecard
from feiyue_core.evaluation.trace_fixture import BenchmarkTraceFixture
from feiyue_core.schemas.common import FeiyueModel


class StrategyComparisonReport(FeiyueModel):
    """Provider-free comparison of multiple strategy scorecards."""

    report_id: str
    scorecards: list[StrategyScorecard]
    best_pass_rate_strategy: str
    lowest_average_cost_strategy: str
    lowest_teacher_call_rate_strategy: str
    unsafe_counts: dict[str, int] = Field(default_factory=dict)
    source_ids: list[str]

    @field_validator("report_id")
    @classmethod
    def _validate_report_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("report_id must be non-empty")
        return normalized

    @field_validator("scorecards")
    @classmethod
    def _validate_scorecards(cls, scorecards: list[StrategyScorecard]) -> list[StrategyScorecard]:
        if not scorecards:
            raise ValueError("scorecards must contain at least one scorecard")
        return scorecards

    @field_validator("best_pass_rate_strategy", "lowest_average_cost_strategy", "lowest_teacher_call_rate_strategy")
    @classmethod
    def _validate_strategy_reference(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("strategy references must be non-empty")
        return normalized

    @field_validator("source_ids")
    @classmethod
    def _validate_source_ids(cls, source_ids: list[str]) -> list[str]:
        if not source_ids:
            raise ValueError("source_ids must contain at least one source id")

        normalized_ids: list[str] = []
        for source_id in source_ids:
            normalized = str(source_id).strip()
            if not normalized:
                raise ValueError("source_ids must not contain empty source ids")
            normalized_ids.append(normalized)
        return normalized_ids

    def render_markdown(self) -> str:
        """Render deterministic Markdown for the comparison report."""

        sorted_scorecards = sorted(self.scorecards, key=lambda scorecard: scorecard.strategy_id)
        sorted_unsafe_counts = sorted(self.unsafe_counts.items())
        return "\n".join(
            [
                f"# Strategy Comparison Report: {self.report_id}",
                "",
                f"- Best Pass Rate Strategy: {self.best_pass_rate_strategy}",
                f"- Lowest Average Cost Strategy: {self.lowest_average_cost_strategy}",
                f"- Lowest Teacher Call Rate Strategy: {self.lowest_teacher_call_rate_strategy}",
                "",
                "## Strategy Summary",
                *[
                    (
                        f"- {scorecard.strategy_id}: pass rate {scorecard.pass_rate:.2f}, "
                        f"average cost {scorecard.average_cost:.2f}, "
                        f"teacher call rate {scorecard.teacher_call_rate:.2f}, "
                        f"unsafe {scorecard.unsafe}, "
                        f"cost-normalized quality {cost_normalized_quality(scorecard):.2f}"
                    )
                    for scorecard in sorted_scorecards
                ],
                "",
                "## Unsafe Counts",
                *[f"- {strategy_id}: {unsafe_count}" for strategy_id, unsafe_count in sorted_unsafe_counts],
                "",
                "## Sources",
                *[f"- {source_id}" for source_id in self.source_ids],
            ]
        )


class BenchmarkStrategyMetrics(FeiyueModel):
    """Provider-free aggregate metrics for one benchmark fixture strategy."""

    strategy_id: str
    total: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    teacher_call_rate: float = Field(ge=0.0)
    weak_autonomy_rate: float = Field(ge=0.0, le=1.0)
    repeated_mistake_count: int = Field(ge=0)
    cost_normalized_quality: float = Field(ge=0.0)
    regression: bool

    @field_validator("strategy_id")
    @classmethod
    def _validate_strategy_id(cls, value: str) -> str:
        return _non_empty(value, "strategy_id")


class BenchmarkStrategyComparison(FeiyueModel):
    """Deterministic comparison metrics across benchmark trace fixtures."""

    comparison_id: str
    baseline_strategy_id: str
    metrics: list[BenchmarkStrategyMetrics]

    @field_validator("comparison_id", "baseline_strategy_id")
    @classmethod
    def _validate_required_string(cls, value: str) -> str:
        return _non_empty(value, "value")

    @field_validator("metrics")
    @classmethod
    def _validate_metrics(cls, value: list[BenchmarkStrategyMetrics]) -> list[BenchmarkStrategyMetrics]:
        if len(value) < 2:
            raise ValueError("metrics must include at least two strategies")
        return value

    def metric_for(self, strategy_id: str) -> BenchmarkStrategyMetrics:
        """Return metrics for a strategy id or raise KeyError."""

        normalized = _non_empty(strategy_id, "strategy_id")
        for metric in self.metrics:
            if metric.strategy_id == normalized:
                return metric
        raise KeyError(normalized)


def build_strategy_comparison_report(
    report_id: str, scorecards: Iterable[StrategyScorecard]
) -> StrategyComparisonReport:
    """Build a deterministic comparison report from strategy scorecards."""

    normalized_report_id = _non_empty(report_id, "report_id")
    sorted_scorecards = sorted(list(scorecards), key=lambda scorecard: scorecard.strategy_id)
    if not sorted_scorecards:
        raise ValueError("scorecards must contain at least one scorecard")

    return StrategyComparisonReport(
        report_id=normalized_report_id,
        scorecards=sorted_scorecards,
        best_pass_rate_strategy=_best_pass_rate_strategy(sorted_scorecards),
        lowest_average_cost_strategy=_lowest_average_cost_strategy(sorted_scorecards),
        lowest_teacher_call_rate_strategy=_lowest_teacher_call_rate_strategy(sorted_scorecards),
        unsafe_counts={scorecard.strategy_id: scorecard.unsafe for scorecard in sorted_scorecards},
        source_ids=_collect_source_ids(sorted_scorecards),
    )


def build_benchmark_strategy_comparison(
    comparison_id: str, fixtures: Iterable[BenchmarkTraceFixture], *, baseline_strategy_id: str = "strong-reference"
) -> BenchmarkStrategyComparison:
    """Aggregate provider-free trace fixtures into comparison metrics."""

    normalized_comparison_id = _non_empty(comparison_id, "comparison_id")
    normalized_baseline = _non_empty(baseline_strategy_id, "baseline_strategy_id")
    fixture_list = sorted(list(fixtures), key=lambda fixture: _strategy_sort_key(fixture.strategy_id))
    if len(fixture_list) < 2:
        raise ValueError("benchmark comparison requires at least two strategies")

    baseline_fixture = next((fixture for fixture in fixture_list if fixture.strategy_id == normalized_baseline), None)
    baseline_pass_rate = _fixture_pass_rate(baseline_fixture) if baseline_fixture is not None else 1.0

    metrics = [
        _metrics_for_fixture(fixture, baseline_strategy_id=normalized_baseline, baseline_pass_rate=baseline_pass_rate)
        for fixture in fixture_list
    ]
    return BenchmarkStrategyComparison(
        comparison_id=normalized_comparison_id,
        baseline_strategy_id=normalized_baseline,
        metrics=metrics,
    )


def cost_normalized_quality(scorecard: StrategyScorecard) -> float:
    """Return pass rate normalized by average cost, treating zero average cost as one."""

    return scorecard.pass_rate / (scorecard.average_cost or 1.0)


_BENCHMARK_STRATEGY_ORDER = {
    "strong-reference": 0,
    "weak+task-contract": 1,
    "weak+sparse-teacher": 2,
    "weak+verifier": 3,
    "weak-only": 4,
}


def _strategy_sort_key(strategy_id: str) -> tuple[int, str]:
    return (_BENCHMARK_STRATEGY_ORDER.get(strategy_id, len(_BENCHMARK_STRATEGY_ORDER)), strategy_id)


def _metrics_for_fixture(
    fixture: BenchmarkTraceFixture, *, baseline_strategy_id: str, baseline_pass_rate: float
) -> BenchmarkStrategyMetrics:
    total = len(fixture.records)
    passed = sum(1 for record in fixture.records if _optional_string(record.outcome) == "passed")
    teacher_calls = sum(record.teacher_call_count for record in fixture.records)
    autonomous = sum(1 for record in fixture.records if record.weak_autonomous)
    mistakes = sum(record.repeated_mistake_count for record in fixture.records)
    cost_total = sum(record.cost_units for record in fixture.records)
    pass_rate = passed / total if total else 0.0
    average_cost = cost_total / total if total else 0.0
    return BenchmarkStrategyMetrics(
        strategy_id=fixture.strategy_id,
        total=total,
        pass_rate=pass_rate,
        teacher_call_rate=teacher_calls / total if total else 0.0,
        weak_autonomy_rate=autonomous / total if total else 0.0,
        repeated_mistake_count=mistakes,
        cost_normalized_quality=pass_rate / (average_cost or 1.0),
        regression=fixture.strategy_id != baseline_strategy_id and (pass_rate < baseline_pass_rate or mistakes > 0),
    )


def _fixture_pass_rate(fixture: BenchmarkTraceFixture | None) -> float:
    if fixture is None or not fixture.records:
        return 0.0
    return sum(1 for record in fixture.records if _optional_string(record.outcome) == "passed") / len(fixture.records)


def _best_pass_rate_strategy(scorecards: list[StrategyScorecard]) -> str:
    return min(scorecards, key=lambda scorecard: (-scorecard.pass_rate, scorecard.strategy_id)).strategy_id


def _lowest_average_cost_strategy(scorecards: list[StrategyScorecard]) -> str:
    return min(scorecards, key=lambda scorecard: (scorecard.average_cost, scorecard.strategy_id)).strategy_id


def _lowest_teacher_call_rate_strategy(scorecards: list[StrategyScorecard]) -> str:
    return min(scorecards, key=lambda scorecard: (scorecard.teacher_call_rate, scorecard.strategy_id)).strategy_id


def _collect_source_ids(scorecards: list[StrategyScorecard]) -> list[str]:
    source_ids: list[str] = []
    seen: set[str] = set()
    for scorecard in scorecards:
        for source_id in scorecard.source_ids:
            if source_id not in seen:
                source_ids.append(source_id)
                seen.add(source_id)
    return source_ids


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    candidate = getattr(value, "value", value)
    normalized = str(candidate).strip()
    return normalized or None


def _non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized
