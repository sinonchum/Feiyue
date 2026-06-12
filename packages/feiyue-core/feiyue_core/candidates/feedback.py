from __future__ import annotations

from pydantic import Field

from feiyue_core.schemas import VerificationResult
from feiyue_core.schemas.common import FeiyueModel


class VerificationFeedback(FeiyueModel):
    verification_result_id: str
    passed: bool
    category: str
    summary: str
    action_items: list[str] = Field(default_factory=list)
    evidence_excerpt: str = ""


class FeedbackAnalyzer:
    def analyze(self, result: VerificationResult) -> VerificationFeedback:
        if result.passed:
            return VerificationFeedback(
                verification_result_id=result.id,
                passed=True,
                category="passed",
                summary=f"{result.verifier_name} passed",
                action_items=["Promote candidate or run next acceptance gate"],
                evidence_excerpt=self._excerpt(result),
            )
        category = result.failure_category or "unknown_failure"
        return VerificationFeedback(
            verification_result_id=result.id,
            passed=False,
            category=category,
            summary=f"{result.verifier_name} failed: {category}",
            action_items=self._action_items(result),
            evidence_excerpt=self._excerpt(result),
        )

    @staticmethod
    def _excerpt(result: VerificationResult) -> str:
        output = result.metadata.get("stdout") or result.metadata.get("stderr") or ""
        return str(output).strip()[:500]

    @staticmethod
    def _action_items(result: VerificationResult) -> list[str]:
        if result.verifier_name == "pytest":
            return ["Inspect failing assertion output", "Rerun pytest after candidate revision"]
        return ["Inspect verifier evidence", "Revise candidate and rerun verifier"]
