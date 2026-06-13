from __future__ import annotations

import json
from pathlib import Path

import pytest

from feiyue_core.evaluation.live_benchmark import BenchmarkAuthorization, BenchmarkRunStatus, StrategyRole
from feiyue_core.evaluation.live_benchmark_runner import (
    AuthorizedLiveBenchmarkRunner,
    LiveBenchmarkCase,
    LiveBenchmarkProfileBinding,
)
from feiyue_core.providers.profile_runner import ProfileRunRequest, ProfileRunResult


class RecordingProfileRunner:
    def __init__(self, results: dict[tuple[str, str], ProfileRunResult]) -> None:
        self.results = results
        self.requests: list[ProfileRunRequest] = []

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        self.requests.append(request)
        return self.results.get(
            (request.profile, request.prompt),
            ProfileRunResult(stdout="", stderr="missing fake result", exit_code=127),
        )


def _authorization(*, scopes: list[str] | None = None, metadata: dict[str, object] | None = None) -> BenchmarkAuthorization:
    return BenchmarkAuthorization(
        authorization_id="auth.wave4.fake",
        authorized_by="test-suite",
        evidence_ids=["ticket:wave4-1A", "fixture:fake-profile-runner"],
        scopes=scopes or ["live_benchmark_execute"],
        metadata=metadata or {},
    )


def _case(case_id: str = "case.alpha", *, marker: str = "OK") -> LiveBenchmarkCase:
    return LiveBenchmarkCase(
        case_id=case_id,
        prompt=f"solve {case_id}",
        expected_markers=[marker],
        source_ids=[f"fixture:{case_id}"],
    )


def _rubric_case(
    case_id: str = "case.rubric",
    *,
    marker: str = "OK",
    required_concepts: list[str] | None = None,
    forbidden_claims: list[str] | None = None,
    min_quality_score: float = 1.0,
) -> LiveBenchmarkCase:
    return LiveBenchmarkCase(
        case_id=case_id,
        prompt=f"solve {case_id}",
        expected_markers=[marker],
        required_concepts=required_concepts or ["preserve marker behavior", "deterministic substring rubric"],
        forbidden_claims=forbidden_claims or [],
        min_quality_score=min_quality_score,
        source_ids=[f"fixture:{case_id}"],
    )


def _bindings() -> list[LiveBenchmarkProfileBinding]:
    return [
        LiveBenchmarkProfileBinding(strategy_role=StrategyRole.WEAK_ONLY, profile="weak.fake"),
        LiveBenchmarkProfileBinding(strategy_role=StrategyRole.STRONG_REFERENCE, profile="strong.fake"),
    ]


def test_missing_authorization_blocks_execution_and_never_calls_provider() -> None:
    runner = RecordingProfileRunner({})
    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="missing-auth",
        cases=[_case()],
        bindings=_bindings(),
        authorization=None,
    )

    assert report.status == BenchmarkRunStatus.BLOCKED
    assert report.provider_call_count == 0
    assert runner.requests == []
    assert "missing_live_benchmark_execute_authorization" in report.reason_codes


def test_plan_only_authorization_blocks_execution_and_never_calls_provider() -> None:
    runner = RecordingProfileRunner({})
    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="plan-only-auth",
        cases=[_case()],
        bindings=_bindings(),
        authorization=_authorization(scopes=["live_benchmark_plan"]),
    )

    assert report.status == BenchmarkRunStatus.BLOCKED
    assert report.provider_call_count == 0
    assert runner.requests == []
    assert "authorization_scope_live_benchmark_execute_missing" in report.reason_codes


def test_fake_runner_executes_bindings_builds_records_and_comparison_from_markers() -> None:
    cases = [_case("case.alpha", marker="OK"), _case("case.beta", marker="PASS")]
    results = {
        ("weak.fake", "solve case.alpha"): ProfileRunResult(stdout="OK weak answer", stderr="", exit_code=0),
        ("weak.fake", "solve case.beta"): ProfileRunResult(stdout="weak misses marker", stderr="", exit_code=0),
        ("strong.fake", "solve case.alpha"): ProfileRunResult(stdout="OK strong answer", stderr="", exit_code=0),
        ("strong.fake", "solve case.beta"): ProfileRunResult(stdout="PASS strong answer", stderr="", exit_code=0),
    }
    runner = RecordingProfileRunner(results)

    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="fake-execution",
        cases=cases,
        bindings=_bindings(),
        authorization=_authorization(),
    )

    assert report.status == "executed"
    assert report.provider_call_count == 4
    assert len(runner.requests) == 4
    assert report.case_count == 2
    assert report.comparison is not None
    assert report.comparison.metric_for("weak-only").pass_rate == 0.5
    assert report.comparison.metric_for("strong-reference").pass_rate == 1.0
    weak_records = [record for record in report.records if record.strategy_id == "weak-only"]
    assert [record.outcome for record in weak_records] == ["passed", "failed"]


def test_required_concepts_case_insensitive_substrings_distinguish_marker_only_from_real_answer() -> None:
    case = _rubric_case()
    runner = RecordingProfileRunner(
        {
            ("weak.fake", "solve case.rubric"): ProfileRunResult(stdout="OK shallow marker only", stderr="", exit_code=0),
            ("strong.fake", "solve case.rubric"): ProfileRunResult(
                stdout="OK answer should PRESERVE MARKER BEHAVIOR with a deterministic substring rubric",
                stderr="",
                exit_code=0,
            ),
        }
    )

    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="rubric-concepts",
        cases=[case],
        bindings=_bindings(),
        authorization=_authorization(),
    )

    weak = next(result for result in report.run_results if result.strategy_id == "weak-only")
    strong = next(result for result in report.run_results if result.strategy_id == "strong-reference")
    assert weak.marker_passed is True
    assert weak.quality_score == 0.5
    assert weak.missing_concepts == ["preserve marker behavior", "deterministic substring rubric"]
    assert weak.passed is False
    assert strong.concept_hits == ["preserve marker behavior", "deterministic substring rubric"]
    assert strong.quality_score == 1.0
    assert strong.passed is True
    assert report.comparison is not None
    assert report.comparison.metric_for("weak-only").pass_rate == 0.0
    assert report.average_quality_score_by_strategy == {"strong-reference": 1.0, "weak-only": 0.5}


def test_forbidden_claim_fails_even_when_marker_and_required_concepts_pass() -> None:
    case = _rubric_case(forbidden_claims=["guaranteed production safe"])
    runner = RecordingProfileRunner(
        {
            ("weak.fake", "solve case.rubric"): ProfileRunResult(
                stdout=(
                    "OK preserve marker behavior; deterministic substring rubric; "
                    "this is guaranteed production safe"
                ),
                stderr="",
                exit_code=0,
            ),
            ("strong.fake", "solve case.rubric"): ProfileRunResult(
                stdout="OK preserve marker behavior; deterministic substring rubric",
                stderr="",
                exit_code=0,
            ),
        }
    )

    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="rubric-forbidden",
        cases=[case],
        bindings=_bindings(),
        authorization=_authorization(),
    )

    weak = next(result for result in report.run_results if result.strategy_id == "weak-only")
    assert weak.marker_passed is True
    assert weak.concept_hits == ["preserve marker behavior", "deterministic substring rubric"]
    assert weak.forbidden_claim_hits == ["guaranteed production safe"]
    assert weak.quality_score == 1.0
    assert weak.passed is False


def test_negated_forbidden_claims_do_not_fail_rubric() -> None:
    case = _rubric_case(forbidden_claims=["human review is unnecessary", "unbounded spending"])
    runner = RecordingProfileRunner(
        {
            ("weak.fake", "solve case.rubric"): ProfileRunResult(
                stdout=(
                    "OK preserve marker behavior; deterministic substring rubric. "
                    "This does not mean human review is unnecessary, and no unbounded spending is allowed."
                ),
                stderr="",
                exit_code=0,
            ),
            ("strong.fake", "solve case.rubric"): ProfileRunResult(
                stdout="OK preserve marker behavior; deterministic substring rubric",
                stderr="",
                exit_code=0,
            ),
        }
    )

    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="rubric-negated-forbidden",
        cases=[case],
        bindings=_bindings(),
        authorization=_authorization(),
    )

    weak = next(result for result in report.run_results if result.strategy_id == "weak-only")
    assert weak.forbidden_claim_hits == []
    assert weak.passed is True


def test_min_quality_score_threshold_controls_pass_fail() -> None:
    case = _rubric_case(min_quality_score=0.75)
    runner = RecordingProfileRunner(
        {
            ("weak.fake", "solve case.rubric"): ProfileRunResult(
                stdout="OK preserve marker behavior but misses the other rubric item",
                stderr="",
                exit_code=0,
            ),
            ("strong.fake", "solve case.rubric"): ProfileRunResult(
                stdout="OK preserve marker behavior and deterministic substring rubric",
                stderr="",
                exit_code=0,
            ),
        }
    )

    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="rubric-threshold",
        cases=[case],
        bindings=_bindings(),
        authorization=_authorization(),
    )

    weak = next(result for result in report.run_results if result.strategy_id == "weak-only")
    strong = next(result for result in report.run_results if result.strategy_id == "strong-reference")
    assert weak.quality_score == 0.75
    assert weak.passed is True
    assert strong.quality_score == 1.0
    assert strong.passed is True


def test_min_quality_score_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError, match="min_quality_score"):
        _rubric_case(min_quality_score=1.01)


def test_max_requests_gate_blocks_before_overrun_without_extra_provider_calls() -> None:
    cases = [_case("case.alpha"), _case("case.beta")]
    runner = RecordingProfileRunner(
        {
            ("weak.fake", "solve case.alpha"): ProfileRunResult(stdout="OK", stderr="", exit_code=0),
            ("strong.fake", "solve case.alpha"): ProfileRunResult(stdout="OK", stderr="", exit_code=0),
        }
    )

    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner).run(
        run_id="max-requests",
        cases=cases,
        bindings=_bindings(),
        authorization=_authorization(metadata={"max_requests": 2}),
    )

    assert report.status == BenchmarkRunStatus.BLOCKED
    assert report.provider_call_count == 2
    assert len(runner.requests) == 2
    assert "max_requests_would_be_exceeded" in report.reason_codes
    assert report.comparison is None


def test_json_and_markdown_evidence_are_written_with_redacted_stdout_stderr(tmp_path: Path) -> None:
    secret = "dummy" + "token" + "value"
    runner = RecordingProfileRunner(
        {
            ("weak.fake", "solve case.alpha"): ProfileRunResult(
                stdout=f"OK api_key={secret}",
                stderr=f"Token {secret}",
                exit_code=0,
            ),
            ("strong.fake", "solve case.alpha"): ProfileRunResult(stdout="OK", stderr="", exit_code=0),
        }
    )

    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner, project_root=tmp_path).run(
        run_id="evidence-redaction",
        cases=[_case()],
        bindings=_bindings(),
        authorization=_authorization(),
    )

    assert len(report.evidence_paths) == 2
    json_path = tmp_path / ".hermes" / "live-benchmarks" / "evidence-redaction" / "report.json"
    markdown_path = tmp_path / ".hermes" / "live-benchmarks" / "evidence-redaction" / "report.md"
    assert json_path.exists()
    assert markdown_path.exists()

    json_text = json_path.read_text(encoding="utf-8")
    markdown_text = markdown_path.read_text(encoding="utf-8")
    assert secret not in json_text
    assert secret not in markdown_text
    assert "[REDACTED]" in json_text
    assert "[REDACTED]" in markdown_text
    data = json.loads(json_text)
    assert data["provider_call_count"] == 2
    assert data["average_quality_score_by_strategy"] == {"strong-reference": 1.0, "weak-only": 1.0}
    assert data["run_results"][0]["stdout_redacted"] == "OK api_key=[REDACTED]"
    assert data["run_results"][0]["quality_score"] == 1.0
    assert data["run_results"][0]["missing_concepts"] == []
    assert data["run_results"][0]["forbidden_claim_hits"] == []
    assert "Average Quality Score" in markdown_text
    assert "quality_score=1.00" in markdown_text
    assert "missing_concepts=[]" in markdown_text
    assert "forbidden_claim_hits=[]" in markdown_text


def test_profile_bindings_reject_duplicate_strategy_roles() -> None:
    with pytest.raises(ValueError, match="duplicate strategy_role"):
        AuthorizedLiveBenchmarkRunner(profile_runner=RecordingProfileRunner({})).run(
            run_id="duplicate-role",
            cases=[_case()],
            bindings=[
                LiveBenchmarkProfileBinding(strategy_role=StrategyRole.WEAK_ONLY, profile="weak.a"),
                LiveBenchmarkProfileBinding(strategy_role=StrategyRole.WEAK_ONLY, profile="weak.b"),
            ],
            authorization=_authorization(),
        )
