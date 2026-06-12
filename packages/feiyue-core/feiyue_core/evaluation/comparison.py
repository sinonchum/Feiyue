"""Strategy comparison reports for Feiyue evaluation scorecards."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field, field_validator

from feiyue_core.evaluation.scorecard import StrategyScorecard
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


def cost_normalized_quality(scorecard: StrategyScorecard) -> float:
    """Return pass rate normalized by average cost, treating zero average cost as one."""

    return scorecard.pass_rate / (scorecard.average_cost or 1.0)


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


def _non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized
