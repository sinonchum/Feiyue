from __future__ import annotations

import json
import subprocess
import sys

from feiyue_core.creative.metrics import CreativeProposalDecision, CreativeProposalMetricsCollector


def test_creative_metrics_collector_records_acceptance_and_taste_violation_rates(tmp_path) -> None:
    collector = CreativeProposalMetricsCollector(tmp_path)
    collector.record(
        CreativeProposalDecision(
            proposal_id="creative-a",
            seed_id="seed-1",
            decision="accepted",
            taste_violations=[],
            selected_by="Simon",
            notes="Useful direction.",
        )
    )
    collector.record(
        CreativeProposalDecision(
            proposal_id="creative-b",
            seed_id="seed-1",
            decision="rejected",
            taste_violations=["gradient_ui"],
            selected_by="Simon",
            notes="Violates flat institutional design law.",
        )
    )

    summary = collector.summary()

    assert summary.total_proposals == 2
    assert summary.accepted_count == 1
    assert summary.rejected_count == 1
    assert summary.acceptance_rate == 0.5
    assert summary.taste_violation_count == 1
    assert summary.taste_violation_rate == 0.5
    assert summary.provider_call_count == 0
    assert summary.mutates_state is False
    assert (tmp_path / ".hermes" / "creative-metrics" / "decisions.jsonl").exists()


def test_creative_metrics_cli_records_decision_and_writes_summary(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "creative-metrics-record",
            "--proposal-id",
            "creative-cli",
            "--seed-id",
            "seed-cli",
            "--decision",
            "accepted",
            "--selected-by",
            "Simon",
            "--note",
            "Accepted for future exploration.",
            "--write-summary",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["total_proposals"] == 1
    assert payload["accepted_count"] == 1
    assert payload["acceptance_rate"] == 1.0
    assert payload["provider_call_count"] == 0
    assert payload["mutates_state"] is False
    assert (tmp_path / ".hermes" / "creative-metrics" / "summary.json").exists()
