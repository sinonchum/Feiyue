"""Provider-neutral generation contracts."""

from .structured_output import CandidateOutputError, CandidateOutputParser, ParsedCandidateOutput, ProviderCandidateOutput

__all__ = [
    "CandidateOutputError",
    "CandidateOutputParser",
    "ParsedCandidateOutput",
    "ProviderCandidateOutput",
]
