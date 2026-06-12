from feiyue_core.candidates import CandidateGenerator, FeedbackAnalyzer
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
