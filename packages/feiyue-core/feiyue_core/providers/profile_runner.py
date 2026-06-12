from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileRunRequest(BaseModel):
    """Request to run a named Hermes profile in the Lane V harness.

    The fake runner uses this contract only for deterministic test doubles; it
    never shells out to a real Hermes profile or reads user configuration.
    """

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1)
    role: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("prompt", "role", "profile")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("source_ids")
    @classmethod
    def _non_blank_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("must include at least one source id")
        for source_id in value:
            if not source_id.strip():
                raise ValueError("source ids must be non-empty")
        return value


class ProfileRunResult(BaseModel):
    """Deterministic result of a fake profile run."""

    model_config = ConfigDict(frozen=True)

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class FakeProfileRunner:
    """Profile runner test double backed by canned profile responses.

    This class intentionally performs no subprocess execution and does not touch
    real Hermes configuration. It maps a requested profile name to a canned
    stdout response so higher-level Lane V code can be tested deterministically.
    """

    def __init__(self, responses: Mapping[str, str]) -> None:
        self._responses = dict(responses)

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        response = self._responses.get(request.profile)
        if response is None:
            return ProfileRunResult(
                stdout="",
                stderr=f"profile '{request.profile}' is not configured for FakeProfileRunner",
                exit_code=127,
            )

        return ProfileRunResult(stdout=response, stderr="", exit_code=0)
