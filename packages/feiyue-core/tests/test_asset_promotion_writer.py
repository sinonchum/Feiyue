import json

from feiyue_core.curation.asset_promotion import (
    AssetPromotionStore,
    AssetProposalStatus,
)
from feiyue_core.curation.distillation_proposal import ProposalPatch, build_distillation_proposal


def _proposal(**overrides: object):
    data = {
        "proposal_id": "proposal-1",
        "source_task_id": "task-1",
        "source_input_id": "input-1",
        "patches": [
            ProposalPatch(
                asset_type="lesson",
                target_path="lessons/retry.md",
                summary="Capture retry lesson.",
                proposed_content="Retry flaky checks once.\n",
                source_ids=["trace-1"],
            )
        ],
    }
    data.update(overrides)
    return build_distillation_proposal(**data)


def _approved_store(tmp_path, proposal=None):
    store = AssetPromotionStore(tmp_path)
    store.persist_proposal(proposal or _proposal())
    store.approve("proposal-1", reviewer="reviewer-1", reason="safe", decided_at="stable-time-1")
    return store


def test_approved_proposal_promotes_into_project_local_hermes_asset_with_evidence(tmp_path) -> None:
    store = _approved_store(tmp_path)

    evidence = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="promote to sandbox",
        decided_at="stable-time-2",
        rollback_ref="review-decision-1",
    )

    target = tmp_path / ".hermes" / "lessons" / "retry.md"
    assert target.read_text() == "Retry flaky checks once.\n"
    assert evidence.promoted is True
    assert evidence.reason_codes == []
    assert evidence.proposal_id == "proposal-1"
    assert evidence.target_path == ".hermes/lessons/retry.md"
    assert evidence.content_hash.startswith("sha256:")
    assert evidence.rollback_snapshot["existed"] is False
    assert evidence.rollback_snapshot["rollback_ref"] == "review-decision-1"
    assert store.load_proposal("proposal-1").status is AssetProposalStatus.PROMOTED

    persisted = json.loads((tmp_path / ".hermes" / "asset-proposals" / "proposal-1" / "promotion.json").read_text())
    assert persisted == evidence.model_dump(mode="json")


def test_promotion_fails_closed_without_approval_and_records_evidence(tmp_path) -> None:
    store = AssetPromotionStore(tmp_path)
    store.persist_proposal(_proposal())

    evidence = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="attempt",
        decided_at="stable-time",
        rollback_ref="review-decision-1",
    )

    assert evidence.promoted is False
    assert "approval_missing" in evidence.reason_codes
    assert not (tmp_path / ".hermes" / "lessons" / "retry.md").exists()
    assert store.load_proposal("proposal-1").status is AssetProposalStatus.REVIEW_REQUIRED


def test_promotion_fails_closed_for_rejected_proposal(tmp_path) -> None:
    store = AssetPromotionStore(tmp_path)
    store.persist_proposal(_proposal())
    store.reject("proposal-1", reviewer="reviewer-1", reason="unsafe", decided_at="stable-time")

    evidence = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="attempt",
        decided_at="stable-time",
        rollback_ref="review-decision-1",
    )

    assert evidence.promoted is False
    assert "proposal_rejected" in evidence.reason_codes
    assert not (tmp_path / ".hermes" / "lessons" / "retry.md").exists()


def test_promotion_fails_closed_when_target_escapes_allowlist(tmp_path) -> None:
    proposal = _proposal(
        patches=[
            ProposalPatch(
                asset_type="lesson",
                target_path="../skills/global.md",
                summary="escape",
                proposed_content="nope\n",
                source_ids=["trace-1"],
            )
        ]
    )
    store = _approved_store(tmp_path, proposal)

    evidence = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="attempt",
        decided_at="stable-time",
        rollback_ref="review-decision-1",
    )

    assert evidence.promoted is False
    assert "target_path_not_allowed" in evidence.reason_codes
    assert not (tmp_path / "skills" / "global.md").exists()


def test_promotion_fails_closed_when_duplicate_content_hash_exists(tmp_path) -> None:
    existing = tmp_path / ".hermes" / "lessons" / "existing.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("Retry flaky checks once.\n")
    store = _approved_store(tmp_path)

    evidence = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="attempt",
        decided_at="stable-time",
        rollback_ref="review-decision-1",
    )

    assert evidence.promoted is False
    assert "duplicate_content_hash" in evidence.reason_codes
    assert not (tmp_path / ".hermes" / "lessons" / "retry.md").exists()


def test_promotion_fails_closed_without_rollback_ref(tmp_path) -> None:
    store = _approved_store(tmp_path)

    evidence = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="attempt",
        decided_at="stable-time",
        rollback_ref="",
    )

    assert evidence.promoted is False
    assert "rollback_ref_missing" in evidence.reason_codes
    assert not (tmp_path / ".hermes" / "lessons" / "retry.md").exists()


def test_rollback_simulation_restores_previous_content_and_deletes_new_file(tmp_path) -> None:
    store = _approved_store(tmp_path)
    target = tmp_path / ".hermes" / "lessons" / "retry.md"
    target.parent.mkdir(parents=True)
    target.write_text("old lesson\n")

    evidence = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="replace sandbox asset",
        decided_at="stable-time-2",
        rollback_ref="review-decision-1",
    )
    assert target.read_text() == "Retry flaky checks once.\n"

    rollback = store.simulate_rollback(evidence)

    assert rollback["rolled_back"] is True
    assert target.read_text() == "old lesson\n"
    target.unlink()

    new_proposal = _proposal(proposal_id="proposal-2")
    new_store = AssetPromotionStore(tmp_path)
    new_store.persist_proposal(new_proposal)
    new_store.approve("proposal-2", reviewer="reviewer-1", reason="safe", decided_at="stable-time-3")
    new_evidence = new_store.promote(
        "proposal-2",
        reviewer="reviewer-1",
        reason="new sandbox asset",
        decided_at="stable-time-4",
        rollback_ref="review-decision-2",
    )
    assert target.exists()

    new_rollback = new_store.simulate_rollback(new_evidence)

    assert new_rollback["rolled_back"] is True
    assert not target.exists()
