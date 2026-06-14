from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel


class SemanticReviewStatus(StrEnum):
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    BLOCKED = "blocked"


class SemanticReviewFinding(FeiyueModel):
    finding_type: str
    term: str
    message: str


class SemanticReviewRequest(FeiyueModel):
    review_id: str
    artifact_id: str
    artifact_text: str
    required_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    reviewer_profile: str = "provider-free-semantic-reviewer"


class SemanticReviewEvidence(FeiyueModel):
    review_id: str
    artifact_id: str
    status: SemanticReviewStatus
    reviewer_profile: str
    findings: list[SemanticReviewFinding] = Field(default_factory=list)
    finding_counts: dict[str, int] = Field(default_factory=dict)
    provider_call_count: int = 0
    dry_run_only: bool = True
    mutates_state: bool = False
    global_hermes_config_mutated: bool = False
    written_at: str | None = None


class ProviderFreeSemanticReviewer:
    """Deterministic reviewer seam for rubric evidence; never calls providers."""

    def review(self, request: SemanticReviewRequest, *, project_root: str | Path, write_report: bool = False) -> SemanticReviewEvidence:
        text = request.artifact_text.lower()
        findings: list[SemanticReviewFinding] = []
        for term in request.required_terms:
            if term.lower() not in text:
                findings.append(
                    SemanticReviewFinding(
                        finding_type="missing_required_term",
                        term=term,
                        message=f"Required term is missing: {term}",
                    )
                )
        for term in request.forbidden_terms:
            if term.lower() in text:
                findings.append(
                    SemanticReviewFinding(
                        finding_type="forbidden_term_present",
                        term=term,
                        message=f"Forbidden term is present: {term}",
                    )
                )
        counts = dict(Counter(finding.finding_type for finding in findings))
        evidence = SemanticReviewEvidence(
            review_id=request.review_id,
            artifact_id=request.artifact_id,
            status=SemanticReviewStatus.APPROVED if not findings else SemanticReviewStatus.NEEDS_REVISION,
            reviewer_profile=request.reviewer_profile,
            findings=findings,
            finding_counts=counts,
            provider_call_count=0,
            dry_run_only=True,
            mutates_state=False,
            global_hermes_config_mutated=False,
            written_at=datetime.now(UTC).isoformat(),
        )
        if write_report:
            write_semantic_review_evidence(project_root, evidence)
        return evidence


def write_semantic_review_evidence(project_root: str | Path, evidence: SemanticReviewEvidence) -> Path:
    path = Path(project_root) / ".hermes" / "semantic-reviews" / evidence.review_id / "evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = Path(project_root) / ".hermes" / "semantic-reviews" / evidence.review_id / "report.md"
    report.write_text(render_semantic_review_report(evidence), encoding="utf-8")
    return path


def render_semantic_review_report(evidence: SemanticReviewEvidence) -> str:
    lines = [
        f"# Semantic Review: {evidence.review_id}",
        "",
        f"- artifact_id: {evidence.artifact_id}",
        f"- status: {evidence.status}",
        f"- provider_call_count: {evidence.provider_call_count}",
        f"- dry_run_only: {evidence.dry_run_only}",
        f"- mutates_state: {evidence.mutates_state}",
        "",
        "## Findings",
        "",
    ]
    if not evidence.findings:
        lines.append("- none")
    else:
        for finding in evidence.findings:
            lines.append(f"- {finding.finding_type}: {finding.term} — {finding.message}")
    return "\n".join(lines).rstrip() + "\n"
