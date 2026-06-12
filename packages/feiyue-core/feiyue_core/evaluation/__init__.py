"""Strategy evaluation contracts."""

from feiyue_core.evaluation.benchmark import (
    BenchmarkSuite,
    BenchmarkTask,
    default_toy_benchmark_suite,
)
from feiyue_core.evaluation.comparison import (
    StrategyComparisonReport,
    build_strategy_comparison_report,
    cost_normalized_quality,
)
from feiyue_core.evaluation.record import (
    CreativeAcceptanceStatus,
    StrategyEvaluationRecord,
    StrategyOutcome,
)
from feiyue_core.evaluation.scorecard import StrategyScorecard, build_strategy_scorecard

__all__ = [
    "BenchmarkSuite",
    "BenchmarkTask",
    "CreativeAcceptanceStatus",
    "StrategyComparisonReport",
    "StrategyEvaluationRecord",
    "StrategyOutcome",
    "StrategyScorecard",
    "build_strategy_comparison_report",
    "build_strategy_scorecard",
    "cost_normalized_quality",
    "default_toy_benchmark_suite",
]
