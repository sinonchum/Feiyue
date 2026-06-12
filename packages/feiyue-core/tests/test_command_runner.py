from feiyue_core.sandbox.command_runner import CommandRunner, CommandStatus


def test_command_runner_captures_success_output(tmp_path) -> None:
    runner = CommandRunner(default_timeout_seconds=5)

    result = runner.run(["python3", "-c", "print('hello feiyue')"], cwd=tmp_path)

    assert result.status == CommandStatus.FINISHED
    assert result.exit_code == 0
    assert result.stdout == "hello feiyue\n"
    assert result.stderr == ""
    assert result.duration_ms >= 0


def test_command_runner_marks_nonzero_exit_as_failed(tmp_path) -> None:
    runner = CommandRunner(default_timeout_seconds=5)

    result = runner.run(["python3", "-c", "import sys; print('bad'); sys.exit(3)"], cwd=tmp_path)

    assert result.status == CommandStatus.FAILED
    assert result.exit_code == 3
    assert result.stdout == "bad\n"


def test_command_runner_times_out_without_hanging(tmp_path) -> None:
    runner = CommandRunner(default_timeout_seconds=1)

    result = runner.run(["python3", "-c", "import time; time.sleep(5)"], cwd=tmp_path)

    assert result.status == CommandStatus.TIMEOUT
    assert result.exit_code is None
    assert result.duration_ms >= 0
