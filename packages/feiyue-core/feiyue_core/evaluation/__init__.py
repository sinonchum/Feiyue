"""Strategy evaluation contracts."""

from feiyue_core.evaluation.benchmark import (
    BenchmarkSuite,
    BenchmarkTask,
    default_toy_benchmark_suite,
)
from feiyue_core.evaluation.benchmark_case import (
    BENCHMARK_CASE_SCHEMA_VERSION,
    BenchmarkCase,
)
from feiyue_core.evaluation.comparison import (
    BenchmarkStrategyComparison,
    BenchmarkStrategyMetrics,
    StrategyComparisonReport,
    build_benchmark_strategy_comparison,
    build_strategy_comparison_report,
    cost_normalized_quality,
)
from feiyue_core.evaluation.record import (
    CreativeAcceptanceStatus,
    StrategyEvaluationRecord,
    StrategyOutcome,
)
from feiyue_core.evaluation.scorecard import StrategyScorecard, build_strategy_scorecard
from feiyue_core.evaluation.trace_fixture import (
    BenchmarkTraceFixture,
    BenchmarkTraceRecord,
    default_strategy_trace_fixtures,
)

__all__ = [
    "BENCHMARK_CASE_SCHEMA_VERSION",
    "BenchmarkCase",
    "BenchmarkStrategyComparison",
    "BenchmarkStrategyMetrics",
    "BenchmarkSuite",
    "BenchmarkTask",
    "BenchmarkTraceFixture",
    "BenchmarkTraceRecord",
    "CreativeAcceptanceStatus",
    "StrategyComparisonReport",
    "StrategyEvaluationRecord",
    "StrategyOutcome",
    "StrategyScorecard",
    "build_benchmark_strategy_comparison",
    "build_strategy_comparison_report",
    "build_strategy_scorecard",
    "cost_normalized_quality",
    "default_strategy_trace_fixtures",
    "default_toy_benchmark_suite",
]
