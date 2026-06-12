from feiyue_core.sandbox.command_runner import CommandRunner
from feiyue_core.verifiers.pytest_verifier import PytestVerifier


def test_pytest_verifier_reports_passing_test_suite(tmp_path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")

    verifier = PytestVerifier(CommandRunner(default_timeout_seconds=10))

    result = verifier.verify(tmp_path)

    assert result.passed is True
    assert result.verifier_type == "pytest"
    assert result.verifier_name == "pytest"
    assert result.score == 1.0
    assert result.failure_category is None


def test_pytest_verifier_reports_failing_test_suite(tmp_path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_bad():\n    assert False\n", encoding="utf-8")

    verifier = PytestVerifier(CommandRunner(default_timeout_seconds=10))

    result = verifier.verify(tmp_path)

    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_category == "pytest_failed"
