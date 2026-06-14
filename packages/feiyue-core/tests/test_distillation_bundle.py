from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from feiyue_core.curation.asset_promotion import AssetPromotionStore
from feiyue_core.curation.distillation_proposal import ProposalPatch, build_distillation_proposal
from feiyue_core.workflow.review_inbox import ReviewInbox


def _bundle() -> dict[str, object]:
    proposal = build_distillation_proposal(
        proposal_id="bundle-demo",
        source_task_id="task.bundle",
        source_input_id="run.bundle",
        patches=[
            ProposalPatch(
                patch_id="lesson",
                asset_type="lesson",
                target_path=".hermes/lessons/bundle-demo.md",
                summary="Lesson patch",
                proposed_content="# Lesson\n\nUse teacher guidance.\n",
                source_ids=["run.bundle"],
            ),
            ProposalPatch(
                patch_id="regression_eval",
                asset_type="regression_eval",
                target_path=".hermes/evals/bundle-demo.md",
                summary="Eval patch",
                proposed_content="# Eval\n\nAssert retry passes.\n",
                source_ids=["run.bundle"],
            ),
            ProposalPatch(
                patch_id="task_template",
                asset_type="task_template",
                target_path=".hermes/task-templates/bundle-demo.md",
                summary="Template patch",
                proposed_content="# Template\n\nRetry after verifier failure.\n",
                source_ids=["run.bundle"],
            ),
        ],
    )
    return proposal.model_dump(mode="json")


def _approved_store(root: Path) -> AssetPromotionStore:
    store = AssetPromotionStore(root)
    store.persist_proposal(_bundle())
    store.approve(
        "bundle-demo",
        reviewer="reviewer",
        reason="approved bundle evidence",
        decided_at=datetime.now(UTC).isoformat(),
    )
    return store


def test_promotes_distillation_bundle_patches_separately_by_patch_id_and_index(tmp_path: Path) -> None:
    store = _approved_store(tmp_path)

    lesson = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="promote lesson evidence",
        decided_at="2026-06-14T00:00:00+00:00",
        rollback_ref="rollback-lesson",
        patch_id="lesson",
    )
    eval_patch = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="promote eval evidence",
        decided_at="2026-06-14T00:01:00+00:00",
        rollback_ref="rollback-eval",
        patch_id="regression_eval",
    )
    template = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="promote template evidence",
        decided_at="2026-06-14T00:02:00+00:00",
        rollback_ref="rollback-template",
        patch_index=2,
    )

    assert lesson.promoted is True
    assert lesson.patch_id == "lesson"
    assert lesson.patch_index == 0
    assert eval_patch.target_path == ".hermes/evals/bundle-demo.md"
    assert template.target_path == ".hermes/task-templates/bundle-demo.md"
    assert (tmp_path / ".hermes" / "lessons" / "bundle-demo.md").read_text() == "# Lesson\n\nUse teacher guidance.\n"
    assert (tmp_path / ".hermes" / "evals" / "bundle-demo.md").read_text() == "# Eval\n\nAssert retry passes.\n"
    assert (tmp_path / ".hermes" / "task-templates" / "bundle-demo.md").read_text() == "# Template\n\nRetry after verifier failure.\n"

    proposal_dir = tmp_path / ".hermes" / "asset-proposals" / "bundle-demo"
    assert json.loads((proposal_dir / "promotions" / "lesson.json").read_text())["rollback_snapshot"]["rollback_ref"] == "rollback-lesson"
    assert json.loads((proposal_dir / "promotions" / "regression_eval.json").read_text())["target_path"] == ".hermes/evals/bundle-demo.md"
    assert json.loads((proposal_dir / "promotions" / "task_template.json").read_text())["patch_index"] == 2
    assert json.loads((proposal_dir / "proposal.json").read_text())["status"] == "promoted"


def test_bundle_promotion_fails_closed_for_invalid_patch_selection(tmp_path: Path) -> None:
    store = _approved_store(tmp_path)

    bad_id = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="bad patch id evidence",
        decided_at="2026-06-14T00:00:00+00:00",
        rollback_ref="rollback-bad",
        patch_id="missing-patch",
    )
    bad_index = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="bad patch index evidence",
        decided_at="2026-06-14T00:00:00+00:00",
        rollback_ref="rollback-bad-index",
        patch_index=99,
    )

    assert bad_id.promoted is False
    assert "patch_missing" in bad_id.reason_codes
    assert bad_index.promoted is False
    assert "patch_missing" in bad_index.reason_codes
    assert not (tmp_path / ".hermes" / "lessons" / "bundle-demo.md").exists()


def test_bundle_promotion_fails_closed_for_missing_approval_duplicate_content_and_rollback(tmp_path: Path) -> None:
    store = AssetPromotionStore(tmp_path)
    store.persist_proposal(_bundle())

    missing_approval = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="no approval",
        decided_at="2026-06-14T00:00:00+00:00",
        rollback_ref="rollback-missing-approval",
        patch_id="lesson",
    )
    assert missing_approval.promoted is False
    assert "approval_missing" in missing_approval.reason_codes

    store.approve("bundle-demo", reviewer="reviewer", reason="approval", decided_at="2026-06-14T00:01:00+00:00")
    missing_rollback = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="missing rollback",
        decided_at="2026-06-14T00:02:00+00:00",
        patch_id="lesson",
    )
    assert missing_rollback.promoted is False
    assert "rollback_ref_missing" in missing_rollback.reason_codes

    duplicate_dir = tmp_path / ".hermes" / "lessons"
    duplicate_dir.mkdir(parents=True)
    (duplicate_dir / "existing.md").write_text("# Lesson\n\nUse teacher guidance.\n")
    duplicate = store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="duplicate content",
        decided_at="2026-06-14T00:03:00+00:00",
        rollback_ref="rollback-duplicate",
        patch_id="lesson",
    )
    assert duplicate.promoted is False
    assert "duplicate_content_hash" in duplicate.reason_codes

    with pytest.raises(ValidationError):
        store.promote(
            "bundle-demo",
            reviewer="",
            reason="reviewer missing",
            decided_at="2026-06-14T00:04:00+00:00",
            rollback_ref="rollback-reviewer",
            patch_id="lesson",
        )
    with pytest.raises(ValidationError):
        store.promote(
            "bundle-demo",
            reviewer="reviewer",
            reason="",
            decided_at="2026-06-14T00:05:00+00:00",
            rollback_ref="rollback-reason",
            patch_id="lesson",
        )


def test_promote_curator_asset_cli_accepts_patch_id(tmp_path: Path) -> None:
    store = AssetPromotionStore(tmp_path)
    store.persist_proposal(_bundle())

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "feiyue_core.workflow.runs_cli",
            "--root",
            str(tmp_path),
            "promote-curator-asset",
            "--proposal-id",
            "bundle-demo",
            "--patch-id",
            "regression_eval",
            "--reviewer",
            "reviewer",
            "--reason",
            "promote eval patch",
            "--rollback-ref",
            "rollback-cli-eval",
        ],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "PYTHONPATH": f"{Path(__file__).resolve().parents[1]}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
        },
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["promoted"] is True
    assert payload["patch_id"] == "regression_eval"
    assert payload["target_path"] == ".hermes/evals/bundle-demo.md"
    assert (tmp_path / ".hermes" / "evals" / "bundle-demo.md").exists()


def test_review_inbox_shows_approved_bundle_patch_promotion_status(tmp_path: Path) -> None:
    store = _approved_store(tmp_path)
    store.promote(
        "bundle-demo",
        reviewer="reviewer",
        reason="promote one patch",
        decided_at="2026-06-14T00:00:00+00:00",
        rollback_ref="rollback-lesson",
        patch_id="lesson",
    )

    summary = ReviewInbox(tmp_path).summary()

    assert [(item.item_type, item.item_id, item.status, item.recommended_action) for item in summary.items] == [
        (
            "asset_proposal",
            "bundle-demo",
            "pending_promotion:1/3",
            "promote_curator_asset_patch_by_patch_id_or_index",
        )
    ]
