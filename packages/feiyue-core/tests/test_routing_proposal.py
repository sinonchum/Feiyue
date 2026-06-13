import json
import subprocess
import sys

from feiyue_core.workflow.capability_feedback import CapabilityFeedbackAggregator
from feiyue_core.workflow.model_routing_table import ModelRoutingTable
from feiyue_core.workflow.routing_proposal import (
    RoutingApplyGate,
    RoutingApplyStatus,
    RoutingProposalApproval,
    RoutingProposalGenerator,
    recommended_changes_hash,
)


def _write_smoke(root, run_id, *, worker_profile, status):
    smoke_dir = root / ".hermes" / "workflow-smokes" / run_id
    smoke_dir.mkdir(parents=True, exist_ok=True)
    (smoke_dir / "evidence.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "task_id": run_id,
                "status": status,
                "worker_profile": worker_profile,
                "provider_call_count": 1,
                "workflow_report": {
                    "teacher_guidance_events": [],
                    "verification_passed": status == "verified",
                    "promotion_ready": status == "verified",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _prepare_project(root):
    routing_path = root / ".hermes" / "model-routing.yaml"
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    routing_text = ModelRoutingTable.default().render_yaml()
    routing_path.write_text(routing_text, encoding="utf-8")
    _write_smoke(root, "steady-1", worker_profile="steady", status="verified")
    _write_smoke(root, "steady-2", worker_profile="steady", status="verified")
    _write_smoke(root, "fragile-1", worker_profile="fragile", status="needs_teacher")
    feedback = CapabilityFeedbackAggregator(root).write_report()
    return routing_path, routing_text, feedback


def test_routing_proposal_binds_feedback_and_routing_hashes_without_mutation(tmp_path) -> None:
    routing_path, routing_text, feedback = _prepare_project(tmp_path)

    proposal = RoutingProposalGenerator(tmp_path).build_proposal(proposal_id="proposal-001")

    assert proposal.proposal_id == "proposal-001"
    assert proposal.requires_human_approval is True
    assert proposal.routing_table_mutated is False
    assert proposal.source_feedback_hash.startswith("sha256:")
    assert proposal.current_routing_hash.startswith("sha256:")
    assert proposal.evidence_sources == feedback.evidence_sources
    assert routing_path.read_text(encoding="utf-8") == routing_text
    assert any(change.profile == "steady" and change.recommended_action == "consider_promotion" for change in proposal.recommended_changes)
    assert any(change.profile == "fragile" and change.recommended_action == "keep_review" for change in proposal.recommended_changes)


def test_routing_proposal_writer_persists_json_and_markdown(tmp_path) -> None:
    routing_path, routing_text, _feedback = _prepare_project(tmp_path)

    proposal = RoutingProposalGenerator(tmp_path).write_proposal(proposal_id="proposal-002")

    proposal_dir = tmp_path / ".hermes" / "routing-proposals" / "proposal-002"
    assert (proposal_dir / "proposal.json").exists()
    assert (proposal_dir / "proposal.md").exists()
    payload = json.loads((proposal_dir / "proposal.json").read_text(encoding="utf-8"))
    assert payload["proposal_id"] == proposal.proposal_id
    assert payload["routing_table_mutated"] is False
    assert "requires_human_approval: True" in (proposal_dir / "proposal.md").read_text(encoding="utf-8")
    assert routing_path.read_text(encoding="utf-8") == routing_text


def test_runs_cli_routing_proposal_writes_review_only_proposal(tmp_path) -> None:
    routing_path, routing_text, _feedback = _prepare_project(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "routing-proposal",
            "--proposal-id",
            "proposal-cli-001",
            "--write-proposal",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["proposal_id"] == "proposal-cli-001"
    assert payload["requires_human_approval"] is True
    assert payload["routing_table_mutated"] is False
    assert routing_path.read_text(encoding="utf-8") == routing_text
    assert (tmp_path / ".hermes" / "routing-proposals" / "proposal-cli-001" / "proposal.json").exists()


def test_runs_cli_routing_proposal_fails_closed_without_feedback(tmp_path) -> None:
    routing_path = tmp_path / ".hermes" / "model-routing.yaml"
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    routing_text = ModelRoutingTable.default().render_yaml()
    routing_path.write_text(routing_text, encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "routing-proposal", "--proposal-id", "missing"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "capability feedback report not found" in completed.stderr
    assert routing_path.read_text(encoding="utf-8") == routing_text


def test_routing_apply_gate_blocks_without_exact_approval(tmp_path) -> None:
    routing_path, routing_text, _feedback = _prepare_project(tmp_path)
    proposal = RoutingProposalGenerator(tmp_path).write_proposal(proposal_id="proposal-apply-blocked")

    result = RoutingApplyGate(tmp_path).apply_proposal(proposal=proposal, approval=None)

    assert result.status is RoutingApplyStatus.BLOCKED
    assert result.routing_table_mutated is False
    assert result.reason_codes == ["missing_routing_proposal_approval"]
    assert routing_path.read_text(encoding="utf-8") == routing_text
    evidence = json.loads((tmp_path / ".hermes" / "routing-proposals" / proposal.proposal_id / "apply-evidence.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "blocked"


def test_routing_apply_gate_applies_only_exact_approval(tmp_path) -> None:
    routing_path, routing_text, _feedback = _prepare_project(tmp_path)
    proposal = RoutingProposalGenerator(tmp_path).write_proposal(proposal_id="proposal-apply-ok")
    wrong = RoutingProposalApproval(
        approval_id="approval-wrong",
        approved_by="simon",
        proposal_id="different-proposal",
        approved_action="apply_reviewed_routing_proposal",
        source_feedback_hash=proposal.source_feedback_hash,
        current_routing_hash=proposal.current_routing_hash,
        recommended_changes_hash=recommended_changes_hash(proposal.recommended_changes),
        approved_at="2026-06-13T00:00:00+00:00",
        reason="wrong proposal id should block",
    )

    blocked = RoutingApplyGate(tmp_path).apply_proposal(proposal=proposal, approval=wrong)

    assert blocked.status is RoutingApplyStatus.BLOCKED
    assert blocked.reason_codes == ["approval_proposal_id_mismatch"]
    assert routing_path.read_text(encoding="utf-8") == routing_text

    exact = wrong.model_copy(update={"approval_id": "approval-ok", "proposal_id": proposal.proposal_id, "reason": "exact approval"})
    applied = RoutingApplyGate(tmp_path).apply_proposal(proposal=proposal, approval=exact)

    assert applied.status is RoutingApplyStatus.APPLIED
    assert applied.routing_table_mutated is True
    assert applied.reason_codes == ["routing_proposal_approval_applies"]
    updated = ModelRoutingTable.parse_yaml(routing_path.read_text(encoding="utf-8"))
    assert updated.routes["worker"].primary == "steady"


def test_runs_cli_approves_and_applies_routing_proposal(tmp_path) -> None:
    routing_path, _routing_text, _feedback = _prepare_project(tmp_path)
    subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "routing-proposal", "--proposal-id", "proposal-cli-apply", "--write-proposal"],
        text=True,
        capture_output=True,
        check=True,
    )

    approval = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "approve-routing-proposal",
            "--proposal-id",
            "proposal-cli-apply",
            "--approved-by",
            "simon",
            "--approval-id",
            "approval-cli-apply",
            "--reason",
            "approve exact routing proposal",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    approval_payload = json.loads(approval.stdout)
    assert approval_payload["approved_action"] == "apply_reviewed_routing_proposal"

    applied = subprocess.run(
        [sys.executable, "-m", "feiyue_core.workflow.runs_cli", "--root", str(tmp_path), "apply-approved-routing", "--proposal-id", "proposal-cli-apply"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(applied.stdout)
    assert payload["status"] == "applied"
    assert payload["routing_table_mutated"] is True
    assert ModelRoutingTable.parse_yaml(routing_path.read_text(encoding="utf-8")).routes["worker"].primary == "steady"
