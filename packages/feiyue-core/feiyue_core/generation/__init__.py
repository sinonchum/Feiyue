"""Provider-neutral generation contracts."""

from .candidate_service import CandidateService, CandidateServiceError, CandidateServiceResult
from .iteration_loop import CandidateVerifier, ToyIterationLoop, ToyIterationResult
from .prompt_loader import PromptArtifact, PromptTemplateError, PromptTemplateLoader
from .structured_output import CandidateOutputError, CandidateOutputParser, ParsedCandidateOutput, ProviderCandidateOutput
from .trace_replay import IterationResumeContext, IterationResumeContextBuilder, IterationResumePromptBuilder, IterationTraceReader

__all__ = [
    "CandidateOutputError",
    "CandidateOutputParser",
    "CandidateService",
    "CandidateServiceError",
    "CandidateServiceResult",
    "CandidateVerifier",
    "IterationResumeContext",
    "IterationResumeContextBuilder",
    "IterationResumePromptBuilder",
    "IterationTraceReader",
    "ParsedCandidateOutput",
    "PromptArtifact",
    "PromptTemplateError",
    "PromptTemplateLoader",
    "ProviderCandidateOutput",
    "ToyIterationLoop",
    "ToyIterationResult",
]
