from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.capability_feedback import CapabilityFeedbackReport
from feiyue_core.workflow.model_routing_table import MODEL_ROUTING_FILENAME


class RoutingProposalError(RuntimeError):
    pass


class RoutingProposalChange(FeiyueModel):
    profile: str
    recommended_action: str
    reason: str
    target_role: str = "worker"
    mutates_routing_table: bool = False


class RoutingUpdateProposal(FeiyueModel):
    proposal_id: str
    generated_at: str
    source_feedback_hash: str
    current_routing_hash: str
    recommended_changes: list[RoutingProposalChange]
    evidence_sources: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    routing_table_mutated: bool = False

    def render_markdown(self) -> str:
        lines = [
            "# Routing Update Proposal",
            "",
            f"- proposal_id: {self.proposal_id}",
            f"- generated_at: {self.generated_at}",
            f"- source_feedback_hash: {self.source_feedback_hash}",
            f"- current_routing_hash: {self.current_routing_hash}",
            f"- requires_human_approval: {self.requires_human_approval}",
            f"- routing_table_mutated: {self.routing_table_mutated}",
            "",
            "## Recommended Changes",
        ]
        for change in self.recommended_changes:
            lines.append(f"- {change.profile}: {change.recommended_action} for {change.target_role} — {change.reason} (mutates_routing_table={change.mutates_routing_table})")
        lines.extend(["", "## Evidence Sources"])
        for source in self.evidence_sources:
            lines.append(f"- {source}")
        lines.append("")
        return "\n".join(lines)


class RoutingProposalGenerator:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.feedback_path = self.project_root / ".hermes" / "capability-feedback" / "latest.json"
        self.routing_path = self.project_root / ".hermes" / MODEL_ROUTING_FILENAME

    def build_proposal(self, *, proposal_id: str) -> RoutingUpdateProposal:
        if not self.feedback_path.exists():
            raise RoutingProposalError(f"capability feedback report not found: {self.feedback_path}")
        if not self.routing_path.exists():
            raise RoutingProposalError(f"model routing table not found: {self.routing_path}")
        feedback_text = self.feedback_path.read_text(encoding="utf-8")
        routing_text = self.routing_path.read_text(encoding="utf-8")
        feedback = CapabilityFeedbackReport.model_validate(json.loads(feedback_text))
        changes = [
            RoutingProposalChange(
                profile=recommendation.profile,
                recommended_action=recommendation.action.value,
                reason=recommendation.reason,
                mutates_routing_table=False,
            )
            for recommendation in feedback.recommendations
            if recommendation.action.value != "keep_routing"
        ]
        return RoutingUpdateProposal(
            proposal_id=proposal_id,
            generated_at=datetime.now(UTC).isoformat(),
            source_feedback_hash=_sha256_text(feedback_text),
            current_routing_hash=_sha256_text(routing_text),
            recommended_changes=changes,
            evidence_sources=feedback.evidence_sources,
            reason_codes=_reason_codes(changes),
            requires_human_approval=True,
            routing_table_mutated=False,
        )

    def write_proposal(self, *, proposal_id: str) -> RoutingUpdateProposal:
        proposal = self.build_proposal(proposal_id=proposal_id)
        output_dir = self.project_root / ".hermes" / "routing-proposals" / proposal_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "proposal.json").write_text(proposal.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (output_dir / "proposal.md").write_text(proposal.render_markdown(), encoding="utf-8")
        return proposal


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reason_codes(changes: list[RoutingProposalChange]) -> list[str]:
    codes = [f"{change.recommended_action}:{change.profile}" for change in changes]
    return codes or ["no_routing_changes_recommended"]
