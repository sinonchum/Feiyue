"""Provider-neutral generation contracts."""

from .candidate_service import CandidateService, CandidateServiceError, CandidateServiceResult
from .iteration_loop import CandidateVerifier, ToyIterationLoop, ToyIterationResult
from .prompt_loader import PromptArtifact, PromptTemplateError, PromptTemplateLoader
from .structured_output import CandidateOutputError, CandidateOutputParser, ParsedCandidateOutput, ProviderCandidateOutput

__all__ = [
    "CandidateOutputError",
    "CandidateOutputParser",
    "CandidateService",
    "CandidateServiceError",
    "CandidateServiceResult",
    "CandidateVerifier",
    "ParsedCandidateOutput",
    "PromptArtifact",
    "PromptTemplateError",
    "PromptTemplateLoader",
    "ProviderCandidateOutput",
    "ToyIterationLoop",
    "ToyIterationResult",
]
