"""Authorization-gated fake-first live benchmark execution runner.

The runner owns orchestration and reporting only. It never shells out directly and
is safe to exercise with ``FakeProfileRunner`` or other test doubles. A future
real lane can inject ``HermesProfileSubprocessRunner`` behind the same run()
contract, but execution remains fail-closed without explicit execute scope.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from pydantic import Field, field_validator

from feiyue_core.evaluation.comparison import BenchmarkStrategyComparison, build_benchmark_strategy_comparison
from feiyue_core.evaluation.live_benchmark import BenchmarkAuthorization, BenchmarkRunStatus, StrategyRole
from feiyue_core.evaluation.record import StrategyOutcome
from feiyue_core.evaluation.trace_fixture import BenchmarkTraceFixture, BenchmarkTraceRecord
from feiyue_core.providers.diagnostics import redact_secrets
from feiyue_core.providers.profile_runner import ProfileRunRequest, ProfileRunResult
from feiyue_core.schemas.common import FeiyueModel


class ProfileRunnerLike(Protocol):
    """Minimal injected runner contract used by live benchmark orchestration."""

    def run(self, request: ProfileRunRequest) -> ProfileRunResult: ...


class LiveBenchmarkCase(FeiyueModel):
    """One prompt/case to execute against every requested strategy binding."""

    case_id: str
    prompt: str
    expected_markers: list[str] = Field(default_factory=list)
    required_concepts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    min_quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    source_ids: list[str]

    @field_validator("case_id", "prompt")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _non_empty(value, "case field")

    @field_validator("expected_markers", "required_concepts", "forbidden_claims")
    @classmethod
    def _normalize_rubric_strings(cls, value: list[str]) -> list[str]:
        return [_non_empty(item, "rubric item") for item in value]

    @field_validator("source_ids")
    @classmethod
    def _validate_source_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("source_ids must be non-empty")
        return [_non_empty(source_id, "source_id") for source_id in value]


class LiveBenchmarkProfileBinding(FeiyueModel):
    """Binds a benchmark strategy role to an injected profile runner profile."""

    strategy_role: StrategyRole | str
    profile: str
    role_label: str | None = None
    command_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("profile")
    @classmethod
    def _validate_profile(cls, value: str) -> str:
        return _non_empty(value, "profile")

    @field_validator("role_label")
    @classmethod
    def _validate_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _non_empty(value, "role_label")


class LiveBenchmarkRunResultEvidence(FeiyueModel):
    """Redacted evidence for one injected profile runner result."""

    case_id: str
    strategy_id: str
    profile: str
    exit_code: int
    timed_out: bool = False
    stdout_redacted: str
    stderr_redacted: str
    passed: bool
    marker_passed: bool
    missing_markers: list[str] = Field(default_factory=list)
    concept_hits: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    forbidden_claim_hits: list[str] = Field(default_factory=list)
    quality_score: float = Field(ge=0.0, le=1.0)


class LiveBenchmarkExecutionRecord(FeiyueModel):
    """Live execution record with strategy id plus comparison-compatible outcome."""

    record_id: str
    strategy_id: str
    task_id: str
    outcome: StrategyOutcome | str
    source_ids: list[str]

    @field_validator("record_id", "strategy_id", "task_id")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        return _non_empty(value, "record field")

    @field_validator("source_ids")
    @classmethod
    def _validate_sources(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("source_ids must be non-empty")
        return [_non_empty(source_id, "source_id") for source_id in value]


class LiveBenchmarkExecutionReport(FeiyueModel):
    """Auditable result envelope for an authorized live benchmark execution."""

    run_id: str
    status: str
    provider_call_count: int = Field(ge=0)
    case_count: int = Field(ge=0)
    strategy_roles: list[StrategyRole]
    records: list[LiveBenchmarkExecutionRecord] = Field(default_factory=list)
    trace_fixtures: list[BenchmarkTraceFixture] = Field(default_factory=list)
    comparison: BenchmarkStrategyComparison | None = None
    average_quality_score_by_strategy: dict[str, float] = Field(default_factory=dict)
    evidence_paths: list[str] = Field(default_factory=list)
    reason_codes: list[str]
    authorization: BenchmarkAuthorization | None = None
    run_results: list[LiveBenchmarkRunResultEvidence] = Field(default_factory=list)

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _non_empty(value, "run_id")

    @field_validator("strategy_roles")
    @classmethod
    def _validate_roles(cls, value: list[StrategyRole]) -> list[StrategyRole]:
        if not value:
            raise ValueError("strategy_roles must be non-empty")
        return value

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("reason_codes must be non-empty")
        return [_non_empty(reason, "reason_code") for reason in value]


class AuthorizedLiveBenchmarkRunner:
    """Execute live benchmark cases through an injected ProfileRunner-like dependency."""

    def __init__(self, *, profile_runner: ProfileRunnerLike, project_root: str | Path | None = None) -> None:
        self._profile_runner = profile_runner
        self._project_root = Path(project_root) if project_root is not None else None

    def run(
        self,
        *,
        run_id: str,
        cases: list[LiveBenchmarkCase],
        bindings: list[LiveBenchmarkProfileBinding],
        authorization: BenchmarkAuthorization | None,
    ) -> LiveBenchmarkExecutionReport:
        normalized_run_id = _non_empty(run_id, "run_id")
        normalized_cases = list(cases)
        normalized_bindings = list(bindings)
        strategy_roles = _strategy_roles(normalized_bindings)
        _validate_cases(normalized_cases)
        _validate_unique_roles(strategy_roles)

        if authorization is None:
            return self._blocked_report(
                run_id=normalized_run_id,
                cases=normalized_cases,
                strategy_roles=strategy_roles,
                authorization=None,
                reason_codes=["missing_live_benchmark_execute_authorization"],
            )

        if not authorization.allows("live_benchmark_execute"):
            return self._blocked_report(
                run_id=normalized_run_id,
                cases=normalized_cases,
                strategy_roles=strategy_roles,
                authorization=authorization,
                reason_codes=["authorization_scope_live_benchmark_execute_missing"],
            )

        max_requests = _max_requests(authorization)
        provider_call_count = 0
        records: list[LiveBenchmarkExecutionRecord] = []
        result_evidence: list[LiveBenchmarkRunResultEvidence] = []
        reason_codes = ["live_benchmark_execute_authorized", "profile_runner_injected"]

        for case in normalized_cases:
            for binding in normalized_bindings:
                if max_requests is not None and provider_call_count >= max_requests:
                    fixtures = _fixtures_from_records(records)
                    return self._finalize_report(
                        LiveBenchmarkExecutionReport(
                            run_id=normalized_run_id,
                            status=BenchmarkRunStatus.BLOCKED.value,
                            provider_call_count=provider_call_count,
                            case_count=len(normalized_cases),
                            strategy_roles=strategy_roles,
                            records=records,
                            trace_fixtures=fixtures,
                            comparison=None,
                            reason_codes=[*reason_codes, "max_requests_would_be_exceeded", "comparison_not_available_incomplete_execution"],
                            authorization=authorization,
                            average_quality_score_by_strategy=_average_quality_score_by_strategy(result_evidence),
                            run_results=result_evidence,
                        )
                    )

                request = ProfileRunRequest(
                    prompt=case.prompt,
                    role=_role_value(binding.strategy_role),
                    profile=binding.profile,
                    source_ids=tuple(case.source_ids),
                )
                result = self._profile_runner.run(request)
                provider_call_count += 1

                rubric = _score_result(result, case)
                strategy_id = _role_value(binding.strategy_role)
                outcome = StrategyOutcome.PASSED if rubric.passed else StrategyOutcome.FAILED
                records.append(
                    LiveBenchmarkExecutionRecord(
                        record_id=f"{normalized_run_id}:{strategy_id}:{case.case_id}",
                        strategy_id=strategy_id,
                        task_id=case.case_id,
                        outcome=outcome,
                        source_ids=[*case.source_ids, f"profile:{binding.profile}", f"strategy:{strategy_id}"],
                    )
                )
                result_evidence.append(
                    LiveBenchmarkRunResultEvidence(
                        case_id=case.case_id,
                        strategy_id=strategy_id,
                        profile=binding.profile,
                        exit_code=result.exit_code,
                        timed_out=result.timed_out,
                        stdout_redacted=redact_secrets(result.stdout),
                        stderr_redacted=redact_secrets(result.stderr),
                        passed=rubric.passed,
                        marker_passed=rubric.marker_passed,
                        missing_markers=rubric.missing_markers,
                        concept_hits=rubric.concept_hits,
                        missing_concepts=rubric.missing_concepts,
                        forbidden_claim_hits=rubric.forbidden_claim_hits,
                        quality_score=rubric.quality_score,
                    )
                )

        fixtures = _fixtures_from_records(records)
        comparison, comparison_reason = _comparison_for_requested_roles(normalized_run_id, fixtures, strategy_roles)
        if comparison_reason is not None:
            reason_codes.append(comparison_reason)

        return self._finalize_report(
            LiveBenchmarkExecutionReport(
                run_id=normalized_run_id,
                status="executed",
                provider_call_count=provider_call_count,
                case_count=len(normalized_cases),
                strategy_roles=strategy_roles,
                records=records,
                trace_fixtures=fixtures,
                comparison=comparison,
                average_quality_score_by_strategy=_average_quality_score_by_strategy(result_evidence),
                reason_codes=reason_codes,
                authorization=authorization,
                run_results=result_evidence,
            )
        )

    def _blocked_report(
        self,
        *,
        run_id: str,
        cases: list[LiveBenchmarkCase],
        strategy_roles: list[StrategyRole],
        authorization: BenchmarkAuthorization | None,
        reason_codes: list[str],
    ) -> LiveBenchmarkExecutionReport:
        return self._finalize_report(
            LiveBenchmarkExecutionReport(
                run_id=run_id,
                status=BenchmarkRunStatus.BLOCKED.value,
                provider_call_count=0,
                case_count=len(cases),
                strategy_roles=strategy_roles,
                comparison=None,
                reason_codes=reason_codes,
                authorization=authorization,
            )
        )

    def _finalize_report(self, report: LiveBenchmarkExecutionReport) -> LiveBenchmarkExecutionReport:
        if self._project_root is None:
            return report

        output_dir = self._project_root / ".hermes" / "live-benchmarks" / report.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "report.json"
        markdown_path = output_dir / "report.md"
        json_path.write_text(
            json.dumps(report.model_dump(mode="json", exclude={"evidence_paths"}), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(_render_markdown_report(report), encoding="utf-8")
        return report.model_copy(update={"evidence_paths": [str(json_path), str(markdown_path)]})


def _validate_cases(cases: list[LiveBenchmarkCase]) -> None:
    if not cases:
        raise ValueError("cases must be non-empty")


def _validate_unique_roles(strategy_roles: list[StrategyRole]) -> None:
    seen: set[str] = set()
    for role in strategy_roles:
        role_value = role.value
        if role_value in seen:
            raise ValueError(f"duplicate strategy_role: {role_value}")
        seen.add(role_value)


def _strategy_roles(bindings: list[LiveBenchmarkProfileBinding]) -> list[StrategyRole]:
    if not bindings:
        raise ValueError("bindings must be non-empty")
    return [StrategyRole(binding.strategy_role) for binding in bindings]


def _role_value(role: StrategyRole | str) -> str:
    return StrategyRole(role).value


def _max_requests(authorization: BenchmarkAuthorization) -> int | None:
    raw = authorization.metadata.get("max_requests")
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("authorization metadata max_requests must be an integer")
    if raw < 0:
        raise ValueError("authorization metadata max_requests must be non-negative")
    return raw


class _RubricScore(FeiyueModel):
    passed: bool
    marker_passed: bool
    missing_markers: list[str]
    concept_hits: list[str]
    missing_concepts: list[str]
    forbidden_claim_hits: list[str]
    quality_score: float = Field(ge=0.0, le=1.0)


def _score_result(result: ProfileRunResult, case: LiveBenchmarkCase) -> _RubricScore:
    """Score one runner result with deterministic, provider-free substring rubrics.

    Expected markers preserve the existing case-sensitive stdout substring behavior.
    Required concepts and forbidden claims are case-insensitive stdout substrings;
    no LLM judge or live provider is used for scoring.
    """

    exit_ok = result.exit_code == 0 and not result.timed_out
    missing_markers = [marker for marker in case.expected_markers if marker not in result.stdout]
    marker_passed = not missing_markers
    stdout_lower = result.stdout.lower()
    concept_hits = [concept for concept in case.required_concepts if concept.lower() in stdout_lower]
    missing_concepts = [concept for concept in case.required_concepts if concept.lower() not in stdout_lower]
    forbidden_claim_hits = [claim for claim in case.forbidden_claims if claim.lower() in stdout_lower]
    quality_score = _quality_score(
        marker_passed=marker_passed,
        marker_count=len(case.expected_markers),
        concept_hits=len(concept_hits),
        concept_count=len(case.required_concepts),
        exit_ok=exit_ok,
    )
    passed = exit_ok and marker_passed and not forbidden_claim_hits and quality_score >= case.min_quality_score
    return _RubricScore(
        passed=passed,
        marker_passed=marker_passed,
        missing_markers=missing_markers,
        concept_hits=concept_hits,
        missing_concepts=missing_concepts,
        forbidden_claim_hits=[redact_secrets(claim) for claim in forbidden_claim_hits],
        quality_score=quality_score,
    )


def _quality_score(
    *, marker_passed: bool, marker_count: int, concept_hits: int, concept_count: int, exit_ok: bool
) -> float:
    marker_component = 1.0 if marker_passed else 0.0
    if concept_count:
        concept_component = concept_hits / concept_count
        if marker_count:
            return (marker_component + concept_component) / 2
        return concept_component
    if marker_count:
        return marker_component
    return 1.0 if exit_ok else 0.0


def _average_quality_score_by_strategy(results: list[LiveBenchmarkRunResultEvidence]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for result in results:
        grouped[result.strategy_id].append(result.quality_score)
    return {strategy_id: sum(scores) / len(scores) for strategy_id, scores in sorted(grouped.items()) if scores}


def _fixtures_from_records(records: list[LiveBenchmarkExecutionRecord]) -> list[BenchmarkTraceFixture]:
    grouped: dict[str, list[BenchmarkTraceRecord]] = defaultdict(list)
    for record in records:
        outcome_value = getattr(record.outcome, "value", record.outcome)
        grouped[record.strategy_id].append(
            BenchmarkTraceRecord(
                record_id=record.record_id,
                task_id=record.task_id,
                outcome=outcome_value,
                teacher_call_count=0,
                weak_autonomous=record.strategy_id != StrategyRole.STRONG_REFERENCE.value,
                repeated_mistake_count=0 if outcome_value == StrategyOutcome.PASSED.value else 1,
                cost_units=1.0,
                provider_call_count=0,
                source_ids=record.source_ids,
            )
        )
    return [BenchmarkTraceFixture(strategy_id=strategy_id, records=grouped[strategy_id]) for strategy_id in sorted(grouped)]


def _comparison_for_requested_roles(
    run_id: str,
    fixtures: list[BenchmarkTraceFixture],
    strategy_roles: list[StrategyRole],
) -> tuple[BenchmarkStrategyComparison | None, str | None]:
    requested = {role.value for role in strategy_roles}
    present = {fixture.strategy_id for fixture in fixtures if fixture.records}
    if not requested.issubset(present):
        return None, "comparison_not_available_missing_strategy_records"
    if len(fixtures) < 2:
        return None, "comparison_not_available_requires_two_strategies"
    return build_benchmark_strategy_comparison(run_id, fixtures), None


def _render_markdown_report(report: LiveBenchmarkExecutionReport) -> str:
    lines = [
        f"# Live Benchmark Execution Report: {report.run_id}",
        "",
        f"- Status: {report.status}",
        f"- Provider Calls: {report.provider_call_count}",
        f"- Case Count: {report.case_count}",
        f"- Strategies: {', '.join(role.value for role in report.strategy_roles)}",
        f"- Reason Codes: {', '.join(report.reason_codes)}",
        "",
        "## Result Metrics",
    ]
    if report.comparison is None:
        lines.append("- Comparison: unavailable")
    else:
        for metric in report.comparison.metrics:
            lines.append(
                f"- {metric.strategy_id}: pass rate {metric.pass_rate:.2f}, "
                f"total {metric.total}, repeated mistakes {metric.repeated_mistake_count}"
            )

    lines.extend(["", "## Average Quality Score"])
    if report.average_quality_score_by_strategy:
        for strategy_id, average_quality in sorted(report.average_quality_score_by_strategy.items()):
            lines.append(f"- {strategy_id}: {average_quality:.2f}")
    else:
        lines.append("- unavailable")

    lines.extend(["", "## Redacted Run Snippets"])
    for result in report.run_results:
        lines.extend(
            [
                f"- {result.strategy_id}/{result.case_id}/{result.profile}: "
                f"passed={result.passed}, marker_passed={result.marker_passed}, "
                f"quality_score={result.quality_score:.2f}, exit={result.exit_code}, timed_out={result.timed_out}",
                f"  - missing_markers={result.missing_markers}",
                f"  - concept_hits={result.concept_hits}",
                f"  - missing_concepts={result.missing_concepts}",
                f"  - forbidden_claim_hits={result.forbidden_claim_hits}",
                f"  - stdout: {_snippet(result.stdout_redacted)}",
                f"  - stderr: {_snippet(result.stderr_redacted)}",
            ]
        )
    return "\n".join(lines) + "\n"


def _snippet(text: str, *, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]} [truncated {len(text) - limit} chars]"


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized
