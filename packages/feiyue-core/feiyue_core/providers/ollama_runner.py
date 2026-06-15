from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from pydantic import Field

from feiyue_core.providers.profile_runner import ProfileRunRequest, ProfileRunResult
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.profile_worker_bridge import _parse_candidate_writes


class OllamaCallEvidence(FeiyueModel):
    profile: str
    model: str
    role: str
    source_ids: tuple[str, ...]
    latency_ms: float = Field(ge=0)
    exit_code: int
    timed_out: bool = False
    response_chars: int = Field(ge=0)
    stderr: str = ""


HttpPost = Callable[[str, dict[str, object], int], dict[str, object]]


class OllamaProfileRunner:
    """ProfileRunRequest adapter for a local Ollama model.

    The runner is profile-map based so Feiyue can route to stable profile ids
    (for example ``local-qwen25-coder``) while the local Ollama model tag remains
    replaceable. It performs no Hermes config mutation and returns ordinary
    ProfileRunResult values so existing Feiyue runners can inject it.
    """

    def __init__(
        self,
        *,
        endpoint: str = "http://127.0.0.1:11434",
        model_map: dict[str, str] | None = None,
        temperature: float = 0.0,
        num_predict: int = 512,
        timeout_seconds: int = 120,
        http_post: HttpPost | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model_map = dict(model_map or {})
        self.temperature = temperature
        self.num_predict = num_predict
        self.timeout_seconds = timeout_seconds
        self._http_post = http_post or _default_http_post
        self.calls: list[OllamaCallEvidence] = []

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        model = self.model_map.get(request.profile, request.profile)
        payload: dict[str, object] = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        started = time.perf_counter()
        try:
            response_payload = self._http_post(f"{self.endpoint}/api/generate", payload, self.timeout_seconds)
            latency_ms = (time.perf_counter() - started) * 1000
            stdout = str(response_payload.get("response", ""))
            result = ProfileRunResult(stdout=stdout, stderr="", exit_code=0, timed_out=False)
        except TimeoutError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            result = ProfileRunResult(stdout="", stderr=f"ollama timeout: {exc}", exit_code=124, timed_out=True)
        except urllib.error.URLError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            result = ProfileRunResult(stdout="", stderr=f"ollama url error: {exc}", exit_code=127, timed_out=False)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            result = ProfileRunResult(
                stdout="",
                stderr=f"ollama runner error: {type(exc).__name__}: {exc}",
                exit_code=1,
                timed_out=False,
            )
        self.calls.append(
            OllamaCallEvidence(
                profile=request.profile,
                model=model,
                role=request.role,
                source_ids=tuple(request.source_ids),
                latency_ms=latency_ms,
                exit_code=result.exit_code,
                timed_out=result.timed_out,
                response_chars=len(result.stdout),
                stderr=result.stderr,
            )
        )
        return result


class CandidateWriteRepairingProfileRunner:
    """Retry once when a worker output is not valid Feiyue candidate-writes JSON."""

    def __init__(self, *, inner: object, max_repair_attempts: int = 1) -> None:
        self.inner = inner
        self.max_repair_attempts = max_repair_attempts
        self.repair_attempt_count = 0
        self.last_parse_error: str | None = None

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        result = self.inner.run(request)  # type: ignore[attr-defined]
        if result.exit_code != 0 or result.timed_out:
            return result
        try:
            _parse_candidate_writes(result.stdout)
            return result
        except ValueError as exc:
            self.last_parse_error = str(exc)

        current = result
        for _ in range(self.max_repair_attempts):
            self.repair_attempt_count += 1
            repair_request = ProfileRunRequest(
                prompt=_repair_prompt(original_prompt=request.prompt, invalid_stdout=current.stdout, parse_error=self.last_parse_error or "parse failed"),
                role=request.role,
                profile=request.profile,
                source_ids=(*request.source_ids, "candidate-write-repair"),
            )
            current = self.inner.run(repair_request)  # type: ignore[attr-defined]
            if current.exit_code != 0 or current.timed_out:
                return current
            try:
                _parse_candidate_writes(current.stdout)
                return current
            except ValueError as exc:
                self.last_parse_error = str(exc)
        return current


def _repair_prompt(*, original_prompt: str, invalid_stdout: str, parse_error: str) -> str:
    return (
        "Repair the previous answer into strict Feiyue candidate-writes JSON.\n"
        "Output raw JSON only, no markdown fences, no commentary.\n"
        "Required shape: {\"writes\":[{\"path\":\"relative/path\",\"content\":\"complete file content\"}]}.\n"
        "The writes value must be a non-empty list. Each write must have string path and string content.\n\n"
        f"Original task prompt:\n{original_prompt}\n\n"
        f"Parser error:\n{parse_error}\n\n"
        f"Invalid answer to repair:\n{invalid_stdout}\n"
    )


def _default_http_post(url: str, payload: dict[str, object], timeout_seconds: int) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Ollama response must be a JSON object")
    return parsed
