from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class FeedbackRecommendationAction(StrEnum):
    CONSIDER_PROMOTION = "consider_promotion"
    KEEP_REVIEW = "keep_review"
    KEEP_ROUTING = "keep_routing"


class ProfileCapabilityMetrics(FeiyueModel):
    profile: str
    workflow_runs: int = Field(ge=0)
    verified_runs: int = Field(ge=0)
    needs_teacher_runs: int = Field(ge=0)
    blocked_runs: int = Field(ge=0)
    teacher_guidance_events: int = Field(ge=0)
    provider_call_count: int = Field(ge=0)
    promotion_attempts: int = Field(ge=0)
    promoted_runs: int = Field(ge=0)
    verification_rate: float = Field(ge=0.0, le=1.0)
    promotion_rate: float = Field(ge=0.0, le=1.0)
    teacher_or_blocked_rate: float = Field(ge=0.0, le=1.0)


class CapabilityFeedbackRecommendation(FeiyueModel):
    profile: str
    action: FeedbackRecommendationAction
    reason: str
    mutates_routing_table: bool = False


class CapabilityFeedbackReport(FeiyueModel):
    generated_at: str
    total_workflow_runs: int = Field(ge=0)
    total_promotion_records: int = Field(ge=0)
    profile_metrics: dict[str, ProfileCapabilityMetrics]
    recommendations: list[CapabilityFeedbackRecommendation]
    routing_table_mutated: bool = False
    evidence_sources: list[str] = Field(default_factory=list)

    def render_markdown(self) -> str:
        lines = [
            "# Capability Feedback Report",
            "",
            f"- generated_at: {self.generated_at}",
            f"- total_workflow_runs: {self.total_workflow_runs}",
            f"- total_promotion_records: {self.total_promotion_records}",
            f"- routing_table_mutated: {self.routing_table_mutated}",
            "",
            "## Profile Metrics",
        ]
        for profile in sorted(self.profile_metrics):
            metrics = self.profile_metrics[profile]
            lines.extend(
                [
                    f"### {profile}",
                    f"- workflow_runs: {metrics.workflow_runs}",
                    f"- verified_runs: {metrics.verified_runs}",
                    f"- needs_teacher_runs: {metrics.needs_teacher_runs}",
                    f"- blocked_runs: {metrics.blocked_runs}",
                    f"- teacher_guidance_events: {metrics.teacher_guidance_events}",
                    f"- promotion_attempts: {metrics.promotion_attempts}",
                    f"- promoted_runs: {metrics.promoted_runs}",
                    f"- verification_rate: {metrics.verification_rate:.2f}",
                    f"- promotion_rate: {metrics.promotion_rate:.2f}",
                    f"- teacher_or_blocked_rate: {metrics.teacher_or_blocked_rate:.2f}",
                    "",
                ]
            )
        lines.append("## Recommendations")
        for recommendation in self.recommendations:
            lines.append(f"- {recommendation.profile}: {recommendation.action.value} — {recommendation.reason} (mutates_routing_table={recommendation.mutates_routing_table})")
        lines.append("")
        return "\n".join(lines)


class CapabilityFeedbackAggregator:
    """Aggregate workflow evidence into audit-only capability feedback.

    Wave4-4 deliberately does not mutate `.hermes/model-routing.yaml`; it only
    reports metrics and recommendations that a human/product gate can inspect.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def build_report(self) -> CapabilityFeedbackReport:
        smoke_records = self._load_json_records(self.project_root / ".hermes" / "workflow-smokes", "evidence.json")
        promotion_records = self._load_json_records(self.project_root / ".hermes" / "workflow-promotions", "promotion-evidence.json")
        promotion_by_run_id = {record.get("run_id"): record for record in promotion_records}
        buckets: dict[str, _MutableProfileMetrics] = {}
        evidence_sources: list[str] = []
        for record in smoke_records:
            profile = str(record.get("worker_profile") or "unknown")
            bucket = buckets.setdefault(profile, _MutableProfileMetrics(profile=profile))
            bucket.workflow_runs += 1
            status = str(record.get("status") or "")
            if status == "verified":
                bucket.verified_runs += 1
            elif status == "needs_teacher":
                bucket.needs_teacher_runs += 1
            elif status == "blocked":
                bucket.blocked_runs += 1
            bucket.provider_call_count += _coerce_int(record.get("provider_call_count"))
            workflow_report = record.get("workflow_report") if isinstance(record.get("workflow_report"), dict) else {}
            teacher_events = workflow_report.get("teacher_guidance_events") if isinstance(workflow_report, dict) else []
            if isinstance(teacher_events, list):
                bucket.teacher_guidance_events += len(teacher_events)
            run_id = record.get("run_id")
            promotion = promotion_by_run_id.get(run_id)
            if promotion is not None:
                bucket.promotion_attempts += 1 if promotion.get("promotion_attempted") else 0
                bucket.promoted_runs += 1 if promotion.get("status") == "promoted" else 0
            evidence_sources.append(f"workflow-smokes/{run_id}")

        metrics = {profile: bucket.to_metrics() for profile, bucket in buckets.items()}
        recommendations = [_recommend(metrics[profile]) for profile in sorted(metrics)]
        return CapabilityFeedbackReport(
            generated_at=datetime.now(UTC).isoformat(),
            total_workflow_runs=len(smoke_records),
            total_promotion_records=len(promotion_records),
            profile_metrics=metrics,
            recommendations=recommendations,
            routing_table_mutated=False,
            evidence_sources=evidence_sources,
        )

    def write_report(self) -> CapabilityFeedbackReport:
        report = self.build_report()
        output_dir = self.project_root / ".hermes" / "capability-feedback"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "latest.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (output_dir / "latest.md").write_text(report.render_markdown(), encoding="utf-8")
        return report

    @staticmethod
    def _load_json_records(parent: Path, filename: str) -> list[dict[str, object]]:
        if not parent.exists():
            return []
        records: list[dict[str, object]] = []
        for path in sorted(parent.glob(f"*/{filename}")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                records.append(payload)
        return records


class _MutableProfileMetrics:
    def __init__(self, *, profile: str) -> None:
        self.profile = profile
        self.workflow_runs = 0
        self.verified_runs = 0
        self.needs_teacher_runs = 0
        self.blocked_runs = 0
        self.teacher_guidance_events = 0
        self.provider_call_count = 0
        self.promotion_attempts = 0
        self.promoted_runs = 0

    def to_metrics(self) -> ProfileCapabilityMetrics:
        verification_rate = _safe_rate(self.verified_runs, self.workflow_runs)
        promotion_rate = _safe_rate(self.promoted_runs, self.workflow_runs)
        teacher_or_blocked_rate = _safe_rate(self.needs_teacher_runs + self.blocked_runs, self.workflow_runs)
        return ProfileCapabilityMetrics(
            profile=self.profile,
            workflow_runs=self.workflow_runs,
            verified_runs=self.verified_runs,
            needs_teacher_runs=self.needs_teacher_runs,
            blocked_runs=self.blocked_runs,
            teacher_guidance_events=self.teacher_guidance_events,
            provider_call_count=self.provider_call_count,
            promotion_attempts=self.promotion_attempts,
            promoted_runs=self.promoted_runs,
            verification_rate=verification_rate,
            promotion_rate=promotion_rate,
            teacher_or_blocked_rate=teacher_or_blocked_rate,
        )


def _safe_rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _coerce_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return 0


def _recommend(metrics: ProfileCapabilityMetrics) -> CapabilityFeedbackRecommendation:
    if metrics.workflow_runs >= 2 and metrics.verification_rate >= 0.8 and metrics.teacher_or_blocked_rate == 0:
        return CapabilityFeedbackRecommendation(
            profile=metrics.profile,
            action=FeedbackRecommendationAction.CONSIDER_PROMOTION,
            reason=f"verification_rate={metrics.verification_rate:.2f}; teacher_or_blocked_rate={metrics.teacher_or_blocked_rate:.2f}; promoted_runs={metrics.promoted_runs}",
            mutates_routing_table=False,
        )
    if metrics.teacher_or_blocked_rate >= 0.5:
        return CapabilityFeedbackRecommendation(
            profile=metrics.profile,
            action=FeedbackRecommendationAction.KEEP_REVIEW,
            reason=f"teacher_or_blocked_rate={metrics.teacher_or_blocked_rate:.2f}; verification_rate={metrics.verification_rate:.2f}",
            mutates_routing_table=False,
        )
    return CapabilityFeedbackRecommendation(
        profile=metrics.profile,
        action=FeedbackRecommendationAction.KEEP_ROUTING,
        reason=f"verification_rate={metrics.verification_rate:.2f}; more evidence required",
        mutates_routing_table=False,
    )
