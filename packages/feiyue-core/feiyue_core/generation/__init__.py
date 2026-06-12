"""Provider-neutral generation contracts."""

from .prompt_loader import PromptArtifact, PromptTemplateError, PromptTemplateLoader
from .structured_output import CandidateOutputError, CandidateOutputParser, ParsedCandidateOutput, ProviderCandidateOutput

__all__ = [
    "CandidateOutputError",
    "CandidateOutputParser",
    "ParsedCandidateOutput",
    "PromptArtifact",
    "PromptTemplateError",
    "PromptTemplateLoader",
    "ProviderCandidateOutput",
]
