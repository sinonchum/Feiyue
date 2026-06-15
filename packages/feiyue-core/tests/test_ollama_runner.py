from __future__ import annotations

import json

from feiyue_core.providers.ollama_runner import CandidateWriteRepairingProfileRunner, OllamaProfileRunner
from feiyue_core.providers.profile_runner import FakeProfileRunner, ProfileRunRequest


def test_ollama_profile_runner_maps_profile_and_records_evidence() -> None:
    seen: dict[str, object] = {}

    def fake_post(url: str, payload: dict[str, object], timeout_seconds: int) -> dict[str, object]:
        seen["url"] = url
        seen["payload"] = payload
        seen["timeout_seconds"] = timeout_seconds
        return {"response": "ok from ollama"}

    runner = OllamaProfileRunner(
        endpoint="http://127.0.0.1:11434/",
        model_map={"local-qwen25-coder": "qwen2.5-coder:7b-instruct"},
        temperature=0,
        num_predict=128,
        timeout_seconds=9,
        http_post=fake_post,
    )

    result = runner.run(
        ProfileRunRequest(
            prompt="write code",
            role="worker",
            profile="local-qwen25-coder",
            source_ids=("source-a",),
        )
    )

    assert result.stdout == "ok from ollama"
    assert result.exit_code == 0
    assert seen["url"] == "http://127.0.0.1:11434/api/generate"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "qwen2.5-coder:7b-instruct"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0, "num_predict": 128}
    assert runner.calls[0].profile == "local-qwen25-coder"
    assert runner.calls[0].model == "qwen2.5-coder:7b-instruct"
    assert runner.calls[0].response_chars == len("ok from ollama")


def test_ollama_profile_runner_reports_http_failure_without_raising() -> None:
    def fake_post(_url: str, _payload: dict[str, object], _timeout_seconds: int) -> dict[str, object]:
        raise RuntimeError("boom")

    runner = OllamaProfileRunner(http_post=fake_post)
    result = runner.run(
        ProfileRunRequest(prompt="x", role="worker", profile="model", source_ids=("s",))
    )

    assert result.exit_code == 1
    assert "RuntimeError" in result.stderr
    assert runner.calls[0].exit_code == 1


def test_candidate_write_repairing_profile_runner_retries_parse_failure() -> None:
    valid = json.dumps({"writes": [{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]})
    inner = FakeProfileRunner(
        {
            "local-qwen25-coder": [
                "```json\n{\"writes\": {\"calc.py\": {\"content\": \"bad schema\"}}}\n```",
                valid,
            ]
        }
    )
    runner = CandidateWriteRepairingProfileRunner(inner=inner, max_repair_attempts=1)

    result = runner.run(
        ProfileRunRequest(
            prompt="Produce candidate writes",
            role="worker",
            profile="local-qwen25-coder",
            source_ids=("task",),
        )
    )

    assert result.stdout == valid
    assert result.exit_code == 0
    assert runner.repair_attempt_count == 1
    assert runner.last_parse_error is not None


def test_candidate_write_repairing_profile_runner_skips_retry_for_valid_output() -> None:
    valid = json.dumps({"writes": [{"path": "calc.py", "content": "ok"}]})
    inner = FakeProfileRunner({"local-qwen25-coder": valid})
    runner = CandidateWriteRepairingProfileRunner(inner=inner, max_repair_attempts=1)

    result = runner.run(
        ProfileRunRequest(prompt="x", role="worker", profile="local-qwen25-coder", source_ids=("s",))
    )

    assert result.stdout == valid
    assert runner.repair_attempt_count == 0
