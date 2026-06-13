import json

from feiyue_core.curation.asset_promotion import (
    AssetPromotionError,
    AssetPromotionStore,
    AssetProposalStatus,
)
from feiyue_core.curation.distillation_proposal import (
    ProposalPatch,
    ProposalStatus,
    build_distillation_proposal,
)


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
                proposed_content="Retry flaky checks once.",
                source_ids=["trace-1", "verifier-1"],
            )
        ],
    }
    data.update(overrides)
    return build_distillation_proposal(**data)


def _store(tmp_path):
    return AssetPromotionStore(tmp_path)


def test_persist_proposal_json_round_trip_under_hermes_asset_proposals(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal()

    record = store.persist_proposal(proposal)

    assert record.proposal_id == "proposal-1"
    assert record.status is AssetProposalStatus.REVIEW_REQUIRED
    assert record.provenance["source_task_id"] == "task-1"
    assert record.provenance["source_input_id"] == "input-1"
    assert record.provenance["source_ids"] == ["trace-1", "verifier-1"]

    proposal_path = tmp_path / ".hermes" / "asset-proposals" / "proposal-1" / "proposal.json"
    assert proposal_path.exists()
    persisted = json.loads(proposal_path.read_text())
    assert persisted["proposal_id"] == "proposal-1"
    assert persisted["status"] == "review_required"
    assert persisted["proposal"]["source_task_id"] == "task-1"

    loaded = store.load_proposal("proposal-1")
    assert loaded == record


def test_review_decisions_append_without_overwriting_and_update_status(tmp_path) -> None:
    store = _store(tmp_path)
    store.persist_proposal(_proposal())

    first = store.approve(
        "proposal-1",
        reviewer="reviewer-1",
        reason="Looks safe.",
        decided_at="2026-01-01T00:00:00Z",
    )
    second = store.reject(
        "proposal-1",
        reviewer="reviewer-2",
        reason="Found a problem after approval.",
        decided_at="2026-01-01T00:01:00Z",
    )

    decisions_path = tmp_path / ".hermes" / "asset-proposals" / "proposal-1" / "decisions.jsonl"
    lines = decisions_path.read_text().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["decision"] for line in lines] == ["approve", "reject"]
    assert json.loads(lines[0]) == first.model_dump(mode="json")
    assert json.loads(lines[1]) == second.model_dump(mode="json")
    assert store.load_proposal("proposal-1").status is AssetProposalStatus.REJECTED


def test_rejected_and_unapproved_promotion_are_blocked_fail_closed(tmp_path) -> None:
    store = _store(tmp_path)
    store.persist_proposal(_proposal(proposal_id="needs-review"))
    store.persist_proposal(_proposal(proposal_id="rejected"))
    store.reject("rejected", reviewer="reviewer-1", reason="Unsafe", decided_at="stable-time")

    needs_review = store.promote(
        "needs-review",
        reviewer="reviewer-1",
        reason="promote",
        decided_at="stable-time",
        rollback_ref="review-decision-1",
    )
    rejected = store.promote(
        "rejected",
        reviewer="reviewer-1",
        reason="promote",
        decided_at="stable-time",
        rollback_ref="review-decision-1",
    )

    assert needs_review.promoted is False
    assert "approval_missing" in needs_review.reason_codes
    assert rejected.promoted is False
    assert "proposal_rejected" in rejected.reason_codes

    try:
        store.promote("missing", reviewer="reviewer-1", reason="promote", decided_at="stable-time")
    except AssetPromotionError as exc:
        assert "missing proposal" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("missing proposal should raise")


def test_approved_promotion_writes_safe_artifact_and_updates_status(tmp_path) -> None:
    store = _store(tmp_path)
    store.persist_proposal(_proposal())
    store.approve("proposal-1", reviewer="reviewer-1", reason="Safe", decided_at="stable-time-1")

    promotion = store.promote(
        "proposal-1",
        reviewer="reviewer-1",
        reason="Promote to safe artifact only.",
        decided_at="stable-time-2",
        rollback_ref="review-decision-1",
    )

    assert promotion.promoted is True
    proposal_dir = tmp_path / ".hermes" / "asset-proposals" / "proposal-1"
    promotion_path = proposal_dir / "promotion.json"
    assert promotion_path.exists()
    assert json.loads(promotion_path.read_text()) == promotion.model_dump(mode="json")
    assert (tmp_path / ".hermes" / "lessons" / "retry.md").read_text() == "Retry flaky checks once."
    assert not (tmp_path / ".hermes" / "skills").exists()
    assert store.load_proposal("proposal-1").status is AssetProposalStatus.PROMOTED


def test_secret_like_metadata_is_redacted_when_persisted(tmp_path) -> None:
    store = _store(tmp_path)
    proposal = _proposal()

    record = store.persist_proposal(
        proposal,
        provenance={"teacher_ref": "teacher-1", "password": "short"},
    )

    assert record.provenance["password"] == "[REDACTED]"
    persisted = json.loads(
        (tmp_path / ".hermes" / "asset-proposals" / "proposal-1" / "proposal.json").read_text()
    )
    assert persisted["provenance"]["password"] == "[REDACTED]"
    assert "short" not in json.dumps(persisted)
