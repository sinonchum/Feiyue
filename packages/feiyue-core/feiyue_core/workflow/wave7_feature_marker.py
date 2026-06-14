from __future__ import annotations


def wave7_feature_summary(*, run_id: str, pr_number: int | None = None) -> dict[str, object]:
    """Return safe, reviewable metadata for the Wave7 feature-PR smoke."""

    normalized_run_id = str(run_id).strip()
    if not normalized_run_id:
        raise ValueError("run_id is required")
    return {
        "run_id": normalized_run_id,
        "stage": "wave7-real-feature-pr",
        "draft_pr_only": True,
        "auto_merge": False,
        "mutates_production": False,
        "pr_number": pr_number,
    }
