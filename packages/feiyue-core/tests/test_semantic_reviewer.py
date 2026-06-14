from __future__ import annotations

import json
import subprocess
import sys

from feiyue_core.workflow.semantic_reviewer import ProviderFreeSemanticReviewer, SemanticReviewRequest


def test_provider_free_semantic_reviewer_flags_required_and_forbidden_terms(tmp_path) -> None:
    request = SemanticReviewRequest(
        review_id="review-demo",
        artifact_id="prd-demo",
        artifact_text="This feature has tests but claims automatic production deployment.",
        required_terms=["tests", "rollback"],
        forbidden_terms=["automatic production deployment"],
        reviewer_profile="fake-semantic-reviewer",
    )

    evidence = ProviderFreeSemanticReviewer().review(request, project_root=tmp_path, write_report=True)

    assert evidence.review_id == "review-demo"
    assert evidence.status == "needs_revision"
    assert evidence.provider_call_count == 0
    assert evidence.mutates_state is False
    assert evidence.global_hermes_config_mutated is False
    assert evidence.finding_counts == {"missing_required_term": 1, "forbidden_term_present": 1}
    assert [finding.term for finding in evidence.findings] == ["rollback", "automatic production deployment"]
    evidence_path = tmp_path / ".hermes" / "semantic-reviews" / "review-demo" / "evidence.json"
    assert evidence_path.exists()
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["dry_run_only"] is True
    assert "automatic production deployment" in json.dumps(payload)


def test_semantic_review_cli_writes_provider_free_evidence(tmp_path) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text("Rollback plan exists. Tests pass. No deployment is attempted.", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "semantic-review",
            "--review-id",
            "cli-semantic-review",
            "--artifact-id",
            "phase-b-doc",
            "--artifact-path",
            str(artifact),
            "--required-term",
            "Rollback plan",
            "--required-term",
            "Tests pass",
            "--forbidden-term",
            "automatic production deployment",
            "--write-report",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "approved"
    assert payload["provider_call_count"] == 0
    assert payload["dry_run_only"] is True
    assert payload["findings"] == []
    assert (tmp_path / ".hermes" / "semantic-reviews" / "cli-semantic-review" / "evidence.json").exists()
