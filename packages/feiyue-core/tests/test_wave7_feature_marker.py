from __future__ import annotations

import pytest

from feiyue_core.workflow.wave7_feature_marker import wave7_feature_summary


def test_wave7_feature_summary_records_draft_only_boundaries() -> None:
    summary = wave7_feature_summary(run_id="real-repo-7a-true-multi-student-feature-dry-run", pr_number=7)

    assert summary == {
        "run_id": "real-repo-7a-true-multi-student-feature-dry-run",
        "stage": "wave7-real-feature-pr",
        "draft_pr_only": True,
        "auto_merge": False,
        "mutates_production": False,
        "pr_number": 7,
    }


def test_wave7_feature_summary_rejects_blank_run_id() -> None:
    with pytest.raises(ValueError, match="run_id is required"):
        wave7_feature_summary(run_id="   ")
