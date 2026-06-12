from __future__ import annotations

from typing import Literal

from pydantic import Field, ValidationError

from feiyue_core.candidates import CandidateGenerator
from feiyue_core.providers import ModelProfile, ProviderResponse
from feiyue_core.schemas import Candidate, StrategyVersion, TaskSpec
from feiyue_core.schemas.common import FeiyueModel


class CandidateOutputError(ValueError):
    def __init__(self, *, provider: str, model: str, request_id: str, message: str) -> None:
        self.provider = provider
        self.model = model
        self.request_id = request_id
        self.message = message
        super().__init__(f"invalid candidate output from {provider}/{model} request_id={request_id}: {message}")


class ProviderCandidateOutput(FeiyueModel):
    kind: Literal["candidate"]
    summary: str
    file_writes: dict[str, str] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    must_be_verified_externally: bool = True


class ParsedCandidateOutput(FeiyueModel):
    output: ProviderCandidateOutput
    provider: str
    model: str
    model_role: str
    request_id: str

    def to_candidate(self, *, task: TaskSpec, strategy: StrategyVersion, model_profile: ModelProfile) -> Candidate:
        candidate = CandidateGenerator().generate(task, strategy, self.output.file_writes)
        candidate.summary = self.output.summary
        candidate.metadata.update(
            {
                "provider": self.provider,
                "model": self.model,
                "model_role": model_profile.role.value,
                "request_id": self.request_id,
                "assumptions": self.output.assumptions,
                "risk_notes": self.output.risk_notes,
                "must_be_verified_externally": self.output.must_be_verified_externally,
            }
        )
        return candidate


class CandidateOutputParser:
    def parse_response(self, response: ProviderResponse) -> ParsedCandidateOutput:
        try:
            output = ProviderCandidateOutput.model_validate(response.content)
        except ValidationError as exc:
            raise CandidateOutputError(
                provider=response.provider,
                model=response.model,
                request_id=response.request_id,
                message=str(exc),
            ) from exc
        return ParsedCandidateOutput(
            output=output,
            provider=response.provider,
            model=response.model,
            model_role=response.role.value,
            request_id=response.request_id,
        )
