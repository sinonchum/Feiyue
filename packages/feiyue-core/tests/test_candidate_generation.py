from feiyue_core.candidates import CandidateGenerator, CandidateRevisionLoop, FeedbackAnalyzer
from feiyue_core.schemas import CandidateStatus, StrategyVersion, TaskSpec, TaskStatus, TaskType, VerificationResult, VerifierType


def test_candidate_generator_creates_deterministic_file_write_candidate() -> None:
    task = TaskSpec(
        id="task_gen_001",
        title="Fix add",
        type=TaskType.CODE,
        status=TaskStatus.READY,
        goal="Make add return the sum",
        acceptance_criteria=["pytest passes"],
        metadata={"target_files": ["math_tools.py"]},
    )
    strategy = StrategyVersion(id="strat_basic", name="basic patch", config_hash="cfg123")

    candidate = CandidateGenerator().generate(task, strategy, file_writes={"math_tools.py": "def add(a, b):\n    return a + b\n"})
    repeated = CandidateGenerator().generate(task, strategy, file_writes={"math_tools.py": "def add(a, b):\n    return a + b\n"})

    assert candidate.id == repeated.id
    assert candidate.task_id == "task_gen_001"
    assert candidate.strategy_version_id == "strat_basic"
    assert candidate.status == CandidateStatus.GENERATED
    assert candidate.summary == "basic patch candidate for task_gen_001 touching math_tools.py"
    assert candidate.metadata["file_writes"] == {"math_tools.py": "def add(a, b):\n    return a + b\n"}
    assert candidate.metadata["acceptance_criteria"] == ["pytest passes"]


def test_feedback_analyzer_extracts_failure_feedback_from_verification_output() -> None:
    result = VerificationResult(
        id="verify_001",
        execution_run_id="run_001",
        verifier_type=VerifierType.PYTEST,
        verifier_name="pytest",
        passed=False,
        failure_category="assertion_failed",
        metadata={"stdout": "E       assert -1 == 3\nFAILED tests/test_math_tools.py::test_add"},
    )

    feedback = FeedbackAnalyzer().analyze(result)

    assert feedback.passed is False
    assert feedback.category == "assertion_failed"
    assert feedback.summary == "pytest failed: assertion_failed"
    assert feedback.action_items == ["Inspect failing assertion output", "Rerun pytest after candidate revision"]
    assert feedback.evidence_excerpt == "E       assert -1 == 3\nFAILED tests/test_math_tools.py::test_add"


def test_feedback_analyzer_returns_positive_feedback_for_passing_verification() -> None:
    result = VerificationResult(
        id="verify_002",
        execution_run_id="run_002",
        verifier_type=VerifierType.PYTEST,
        verifier_name="pytest",
        passed=True,
        metadata={"stdout": "1 passed"},
    )

    feedback = FeedbackAnalyzer().analyze(result)

    assert feedback.passed is True
    assert feedback.category == "passed"
    assert feedback.summary == "pytest passed"
    assert feedback.action_items == ["Promote candidate or run next acceptance gate"]


def test_candidate_revision_loop_creates_revised_candidate_from_failure_feedback() -> None:
    task = TaskSpec(
        id="task_rev_001",
        title="Fix add",
        type=TaskType.CODE,
        status=TaskStatus.READY,
        goal="Make add return the sum",
        acceptance_criteria=["pytest passes"],
        metadata={"target_files": ["math_tools.py"]},
    )
    strategy = StrategyVersion(id="strat_basic", name="basic patch", config_hash="cfg123")
    original = CandidateGenerator().generate(
        task,
        strategy,
        file_writes={"math_tools.py": "def add(a, b):\n    return a - b\n"},
    )
    failed_result = VerificationResult(
        id="verify_failed_rev_001",
        execution_run_id="run_failed_rev_001",
        verifier_type=VerifierType.PYTEST,
        verifier_name="pytest",
        passed=False,
        failure_category="assertion_failed",
        metadata={"stdout": "E       assert -1 == 3\nFAILED tests/test_math_tools.py::test_add"},
    )
    feedback = FeedbackAnalyzer().analyze(failed_result)

    revised = CandidateRevisionLoop().revise(
        task=task,
        strategy=strategy,
        parent=original,
        feedback=feedback,
        revised_file_writes={"math_tools.py": "def add(a, b):\n    return a + b\n"},
    )

    assert revised.id != original.id
    assert revised.task_id == original.task_id
    assert revised.strategy_version_id == original.strategy_version_id
    assert revised.status == CandidateStatus.GENERATED
    assert revised.summary == "basic patch revision for task_rev_001 after assertion_failed"
    assert revised.metadata["parent_candidate_id"] == original.id
    assert revised.metadata["revision_reason"] == "pytest failed: assertion_failed"
    assert revised.metadata["feedback_category"] == "assertion_failed"
    assert revised.metadata["revision_index"] == 1
    assert revised.metadata["file_writes"] == {"math_tools.py": "def add(a, b):\n    return a + b\n"}


def test_candidate_revision_loop_increments_revision_index_from_parent_metadata() -> None:
    task = TaskSpec(
        id="task_rev_002",
        title="Fix add",
        type=TaskType.CODE,
        status=TaskStatus.READY,
        goal="Make add return the sum",
    )
    strategy = StrategyVersion(id="strat_basic", name="basic patch", config_hash="cfg123")
    parent = CandidateGenerator().generate(task, strategy, file_writes={"math_tools.py": "bad"})
    parent.metadata["revision_index"] = 2
    feedback = FeedbackAnalyzer().analyze(
        VerificationResult(
            id="verify_failed_rev_002",
            execution_run_id="run_failed_rev_002",
            verifier_type=VerifierType.PYTEST,
            verifier_name="pytest",
            passed=False,
            failure_category="assertion_failed",
        )
    )

    revised = CandidateRevisionLoop().revise(
        task=task,
        strategy=strategy,
        parent=parent,
        feedback=feedback,
        revised_file_writes={"math_tools.py": "better"},
    )

    assert revised.metadata["revision_index"] == 3
