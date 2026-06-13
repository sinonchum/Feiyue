from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.capability_feedback import CapabilityFeedbackReport
from feiyue_core.workflow.model_routing_table import MODEL_ROUTING_FILENAME, ModelRoutingTable, RoleRoute


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


def recommended_changes_hash(changes: list[RoutingProposalChange]) -> str:
    stable = json.dumps([change.model_dump(mode="json") for change in changes], sort_keys=True, separators=(",", ":"))
    return _sha256_text(stable)


class RoutingApplyStatus(StrEnum):
    BLOCKED = "blocked"
    APPLIED = "applied"


class RoutingProposalApproval(FeiyueModel):
    approval_id: str
    approved_by: str
    proposal_id: str
    approved_action: str
    source_feedback_hash: str
    current_routing_hash: str
    recommended_changes_hash: str
    approved_at: str
    reason: str


class RoutingApplyResult(FeiyueModel):
    proposal_id: str
    status: RoutingApplyStatus
    reason_codes: list[str]
    routing_table_mutated: bool
    applied_profiles: list[str] = Field(default_factory=list)
    evidence_path: str | None = None


class RoutingApplyGate:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.routing_path = self.project_root / ".hermes" / MODEL_ROUTING_FILENAME

    def apply_proposal(self, *, proposal: RoutingUpdateProposal, approval: RoutingProposalApproval | None) -> RoutingApplyResult:
        reason = self._block_reason(proposal, approval)
        if reason is not None:
            return self._write_result(
                RoutingApplyResult(
                    proposal_id=proposal.proposal_id,
                    status=RoutingApplyStatus.BLOCKED,
                    reason_codes=[reason],
                    routing_table_mutated=False,
                )
            )
        assert approval is not None
        routing_text = self.routing_path.read_text(encoding="utf-8")
        table = ModelRoutingTable.parse_yaml(routing_text)
        routes = dict(table.routes)
        applied_profiles: list[str] = []
        for change in proposal.recommended_changes:
            if change.recommended_action != "consider_promotion":
                continue
            route = routes.get(change.target_role)
            if route is None:
                continue
            routes[change.target_role] = RoleRoute(
                primary=change.profile,
                fallback=route.fallback,
                reviewer=route.reviewer,
                teacher=route.teacher,
            )
            applied_profiles.append(change.profile)
        updated = ModelRoutingTable(routes=routes).render_yaml()
        mutated = updated != routing_text
        if mutated:
            self.routing_path.write_text(updated, encoding="utf-8")
        return self._write_result(
            RoutingApplyResult(
                proposal_id=proposal.proposal_id,
                status=RoutingApplyStatus.APPLIED,
                reason_codes=["routing_proposal_approval_applies"],
                routing_table_mutated=mutated,
                applied_profiles=applied_profiles,
            )
        )

    def _block_reason(self, proposal: RoutingUpdateProposal, approval: RoutingProposalApproval | None) -> str | None:
        if approval is None:
            return "missing_routing_proposal_approval"
        if approval.proposal_id != proposal.proposal_id:
            return "approval_proposal_id_mismatch"
        if approval.approved_action != "apply_reviewed_routing_proposal":
            return "approval_action_mismatch"
        if approval.source_feedback_hash != proposal.source_feedback_hash:
            return "approval_feedback_hash_mismatch"
        if approval.current_routing_hash != proposal.current_routing_hash:
            return "approval_routing_hash_mismatch"
        if approval.recommended_changes_hash != recommended_changes_hash(proposal.recommended_changes):
            return "approval_recommended_changes_hash_mismatch"
        if _sha256_text(self.routing_path.read_text(encoding="utf-8")) != proposal.current_routing_hash:
            return "current_routing_hash_mismatch"
        return None

    def _write_result(self, result: RoutingApplyResult) -> RoutingApplyResult:
        output_dir = self.project_root / ".hermes" / "routing-proposals" / result.proposal_id
        output_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = output_dir / "apply-evidence.json"
        result = result.model_copy(update={"evidence_path": str(evidence_path)})
        evidence_path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return result


def write_routing_proposal_approval(approval: RoutingProposalApproval, project_root: str | Path) -> Path:
    path = Path(project_root) / ".hermes" / "routing-proposals" / approval.proposal_id / "approval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(approval.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def read_routing_proposal_approval(project_root: str | Path, proposal_id: str) -> RoutingProposalApproval:
    path = Path(project_root) / ".hermes" / "routing-proposals" / proposal_id / "approval.json"
    if not path.exists():
        raise RoutingProposalError(f"routing proposal approval not found: {path}")
    return RoutingProposalApproval.model_validate(json.loads(path.read_text(encoding="utf-8")))


def read_routing_proposal(project_root: str | Path, proposal_id: str) -> RoutingUpdateProposal:
    path = Path(project_root) / ".hermes" / "routing-proposals" / proposal_id / "proposal.json"
    if not path.exists():
        raise RoutingProposalError(f"routing proposal not found: {path}")
    return RoutingUpdateProposal.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reason_codes(changes: list[RoutingProposalChange]) -> list[str]:
    codes = [f"{change.recommended_action}:{change.profile}" for change in changes]
    return codes or ["no_routing_changes_recommended"]
