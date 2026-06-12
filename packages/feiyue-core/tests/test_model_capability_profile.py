from feiyue_core.capability import (
    CapabilityLevelStats,
    ModelCapabilityProfile,
    WorkerPerformanceRecord,
    WorkerTaskResult,
    build_model_capability_profile,
)


def _record(**overrides: object) -> WorkerPerformanceRecord:
    data = {
        "record_id": "record-1",
        "worker_id": "worker-1",
        "model_id": "model-a",
        "task_id": "task-1",
        "capability_level": "single_file_change",
        "result": WorkerTaskResult.PASSED,
        "verifier_result": "verified",
        "teacher_call_count": 0,
        "repeated_mistake_category": None,
        "curation_evidence_ids": ["evidence-1"],
        "review_decision_ids": [],
        "source_ids": ["source-1"],
    }
    data.update(overrides)
    return WorkerPerformanceRecord(**data)


def test_capability_level_stats_rates_handle_zero_and_nonzero_totals() -> None:
    empty = CapabilityLevelStats(
        model_id="model-a",
        capability_level="single_file_change",
        total=0,
        passed=0,
        failed=0,
        blocked=0,
        unsafe=0,
        teacher_call_total=0,
        repeated_mistake_counts={},
        evidence_ids=[],
        review_decision_ids=[],
    )
    populated = CapabilityLevelStats(
        model_id="model-a",
        capability_level="single_file_change",
        total=4,
        passed=3,
        failed=1,
        blocked=0,
        unsafe=0,
        teacher_call_total=2,
        repeated_mistake_counts={},
        evidence_ids=[],
        review_decision_ids=[],
    )

    assert empty.pass_rate == 0.0
    assert empty.teacher_call_rate == 0.0
    assert populated.pass_rate == 0.75
    assert populated.teacher_call_rate == 0.5


def test_build_model_capability_profile_filters_and_aggregates_by_level() -> None:
    records = [
        _record(
            record_id="record-1",
            result=WorkerTaskResult.PASSED,
            teacher_call_count=0,
            curation_evidence_ids=["evidence-1", "record-1"],
            review_decision_ids=["review-1"],
            source_ids=["source-1"],
        ),
        _record(
            record_id="record-2",
            result=WorkerTaskResult.FAILED,
            teacher_call_count=2,
            repeated_mistake_category="missed-edge-case",
            curation_evidence_ids=["evidence-2", "evidence-1"],
            review_decision_ids=["review-2", "review-1"],
            source_ids=["source-2"],
        ),
        _record(
            record_id="record-3",
            capability_level="bounded_debug",
            result=WorkerTaskResult.BLOCKED,
            teacher_call_count=1,
            repeated_mistake_category="missed-edge-case",
            curation_evidence_ids=["evidence-3"],
            review_decision_ids=["review-3"],
            source_ids=["source-3", "source-1"],
        ),
        _record(
            record_id="record-4",
            model_id="model-b",
            result=WorkerTaskResult.UNSAFE,
            teacher_call_count=9,
            repeated_mistake_category="ignored-safety",
            curation_evidence_ids=["other-evidence"],
            review_decision_ids=["other-review"],
            source_ids=["other-source"],
        ),
    ]

    profile = build_model_capability_profile("model-a", records)

    assert isinstance(profile, ModelCapabilityProfile)
    assert set(profile.stats_by_level) == {"single_file_change", "bounded_debug"}

    single_file = profile.stats_by_level["single_file_change"]
    assert single_file.model_id == "model-a"
    assert single_file.total == 2
    assert single_file.passed == 1
    assert single_file.failed == 1
    assert single_file.blocked == 0
    assert single_file.unsafe == 0
    assert single_file.teacher_call_total == 2
    assert single_file.repeated_mistake_counts == {"missed-edge-case": 1}
    assert single_file.evidence_ids == [
        "record-1",
        "evidence-1",
        "source-1",
        "record-2",
        "evidence-2",
        "source-2",
    ]
    assert single_file.review_decision_ids == ["review-1", "review-2"]

    bounded_debug = profile.stats_by_level["bounded_debug"]
    assert bounded_debug.total == 1
    assert bounded_debug.passed == 0
    assert bounded_debug.failed == 0
    assert bounded_debug.blocked == 1
    assert bounded_debug.unsafe == 0
    assert bounded_debug.teacher_call_total == 1
    assert bounded_debug.repeated_mistake_counts == {"missed-edge-case": 1}
    assert bounded_debug.evidence_ids == ["record-3", "evidence-3", "source-3", "source-1"]
    assert bounded_debug.review_decision_ids == ["review-3"]


def test_build_model_capability_profile_counts_all_results() -> None:
    profile = build_model_capability_profile(
        "model-a",
        [
            _record(record_id="passed", result=WorkerTaskResult.PASSED),
            _record(record_id="failed", result=WorkerTaskResult.FAILED),
            _record(record_id="blocked", result=WorkerTaskResult.BLOCKED),
            _record(record_id="unsafe", result=WorkerTaskResult.UNSAFE),
        ],
    )

    stats = profile.stats_by_level["single_file_change"]
    assert stats.total == 4
    assert stats.passed == 1
    assert stats.failed == 1
    assert stats.blocked == 1
    assert stats.unsafe == 1


def test_render_markdown_for_stats_is_deterministic() -> None:
    stats = CapabilityLevelStats(
        model_id="model-a",
        capability_level="single_file_change",
        total=4,
        passed=3,
        failed=1,
        blocked=0,
        unsafe=0,
        teacher_call_total=2,
        repeated_mistake_counts={"z-last": 1, "a-first": 2},
        evidence_ids=["evidence-2", "evidence-1"],
        review_decision_ids=["review-2", "review-1"],
    )

    assert stats.render_markdown() == (
        "## Capability Level: single_file_change\n"
        "\n"
        "- Model: model-a\n"
        "- Total: 4\n"
        "- Passed: 3\n"
        "- Failed: 1\n"
        "- Blocked: 0\n"
        "- Unsafe: 0\n"
        "- Pass Rate: 0.7500\n"
        "- Teacher Calls: 2\n"
        "- Teacher Call Rate: 0.5000\n"
        "\n"
        "**Repeated Mistakes:**\n"
        "- a-first: 2\n"
        "- z-last: 1\n"
        "\n"
        "**Evidence IDs:**\n"
        "- evidence-2\n"
        "- evidence-1\n"
        "\n"
        "**Review Decision IDs:**\n"
        "- review-2\n"
        "- review-1"
    )


def test_render_markdown_for_profile_is_deterministic() -> None:
    profile = ModelCapabilityProfile(
        model_id="model-a",
        stats_by_level={
            "z-level": CapabilityLevelStats(
                model_id="model-a",
                capability_level="z-level",
                total=1,
                passed=0,
                failed=0,
                blocked=0,
                unsafe=1,
                teacher_call_total=0,
                repeated_mistake_counts={},
                evidence_ids=[],
                review_decision_ids=[],
            ),
            "a-level": CapabilityLevelStats(
                model_id="model-a",
                capability_level="a-level",
                total=1,
                passed=1,
                failed=0,
                blocked=0,
                unsafe=0,
                teacher_call_total=1,
                repeated_mistake_counts={},
                evidence_ids=["evidence-a"],
                review_decision_ids=[],
            ),
        },
    )

    markdown = profile.render_markdown()

    assert markdown.startswith("# Model Capability Profile: model-a\n")
    assert markdown.index("## Capability Level: a-level") < markdown.index("## Capability Level: z-level")
    assert "**Repeated Mistakes:**\n- None" in markdown
    assert "**Review Decision IDs:**\n- None" in markdown
