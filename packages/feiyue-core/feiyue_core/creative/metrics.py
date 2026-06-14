from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class CreativeProposalDecision(FeiyueModel):
    proposal_id: str
    seed_id: str
    decision: Literal["accepted", "rejected", "deferred"]
    taste_violations: list[str] = Field(default_factory=list)
    selected_by: str
    notes: str = ""
    decided_at: str | None = None


class CreativeProposalMetricsSummary(FeiyueModel):
    total_proposals: int
    accepted_count: int
    rejected_count: int
    deferred_count: int
    acceptance_rate: float
    taste_violation_count: int
    taste_violation_rate: float
    provider_call_count: int = 0
    mutates_state: bool = False
    global_hermes_config_mutated: bool = False
    written_at: str | None = None


class CreativeProposalMetricsCollector:
    """Append-only local metrics for human decisions on creative proposals."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.metrics_dir = self.project_root / ".hermes" / "creative-metrics"
        self.decisions_path = self.metrics_dir / "decisions.jsonl"

    def record(self, decision: CreativeProposalDecision) -> CreativeProposalDecision:
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        payload = decision.model_dump(mode="json")
        payload["decided_at"] = payload.get("decided_at") or datetime.now(UTC).isoformat()
        self.decisions_path.open("a", encoding="utf-8").write(json.dumps(payload, sort_keys=True) + "\n")
        return CreativeProposalDecision.model_validate(payload)

    def decisions(self) -> list[CreativeProposalDecision]:
        if not self.decisions_path.exists():
            return []
        rows: list[CreativeProposalDecision] = []
        for line in self.decisions_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(CreativeProposalDecision.model_validate_json(line))
        return rows

    def summary(self, *, write_summary: bool = False) -> CreativeProposalMetricsSummary:
        decisions = self.decisions()
        total = len(decisions)
        accepted = sum(1 for decision in decisions if decision.decision == "accepted")
        rejected = sum(1 for decision in decisions if decision.decision == "rejected")
        deferred = sum(1 for decision in decisions if decision.decision == "deferred")
        violations = sum(1 for decision in decisions if decision.taste_violations)
        summary = CreativeProposalMetricsSummary(
            total_proposals=total,
            accepted_count=accepted,
            rejected_count=rejected,
            deferred_count=deferred,
            acceptance_rate=accepted / total if total else 0.0,
            taste_violation_count=violations,
            taste_violation_rate=violations / total if total else 0.0,
            provider_call_count=0,
            mutates_state=False,
            global_hermes_config_mutated=False,
            written_at=datetime.now(UTC).isoformat(),
        )
        if write_summary:
            self.metrics_dir.mkdir(parents=True, exist_ok=True)
            (self.metrics_dir / "summary.json").write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
            (self.metrics_dir / "summary.md").write_text(render_creative_metrics_summary(summary), encoding="utf-8")
        return summary


def render_creative_metrics_summary(summary: CreativeProposalMetricsSummary) -> str:
    return "\n".join(
        [
            "# Creative Proposal Metrics",
            "",
            f"- total_proposals: {summary.total_proposals}",
            f"- accepted_count: {summary.accepted_count}",
            f"- rejected_count: {summary.rejected_count}",
            f"- deferred_count: {summary.deferred_count}",
            f"- acceptance_rate: {summary.acceptance_rate}",
            f"- taste_violation_count: {summary.taste_violation_count}",
            f"- taste_violation_rate: {summary.taste_violation_rate}",
            f"- provider_call_count: {summary.provider_call_count}",
            f"- mutates_state: {summary.mutates_state}",
        ]
    ) + "\n"
