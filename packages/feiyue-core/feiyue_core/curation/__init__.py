"""Curation contracts for provider-free asset distillation."""

from feiyue_core.curation.distillation_proposal import (
    ALLOWED_ASSET_TYPES,
    DistillationProposal,
    ProposalPatch,
    ProposalStatus,
    build_distillation_proposal,
)

__all__ = [
    "ALLOWED_ASSET_TYPES",
    "DistillationProposal",
    "ProposalPatch",
    "ProposalStatus",
    "build_distillation_proposal",
]
