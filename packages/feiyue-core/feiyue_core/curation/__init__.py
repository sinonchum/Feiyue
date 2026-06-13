"""Curation contracts for provider-free asset distillation."""

from feiyue_core.curation.curator_input import CuratorInput
from feiyue_core.curation.asset_promotion import (
    AssetPromotionError,
    AssetPromotionStore,
    AssetProposalRecord,
    AssetProposalStatus,
    AssetReviewDecision,
    PromotionBlockedError,
)
from feiyue_core.curation.distillation_proposal import (
    ALLOWED_ASSET_TYPES,
    DistillationProposal,
    ProposalPatch,
    ProposalStatus,
    build_distillation_proposal,
)
from feiyue_core.curation.review_gate import (
    InvalidReviewTransitionError,
    ReviewDecision,
    ReviewDecisionStatus,
    ReviewGate,
)
from feiyue_core.curation.teacher_guidance import (
    TeacherGuidanceSummary,
    normalize_teacher_guidance,
)

__all__ = [
    "ALLOWED_ASSET_TYPES",
    "AssetPromotionError",
    "AssetPromotionStore",
    "AssetProposalRecord",
    "AssetProposalStatus",
    "AssetReviewDecision",
    "CuratorInput",
    "DistillationProposal",
    "InvalidReviewTransitionError",
    "ProposalPatch",
    "ProposalStatus",
    "PromotionBlockedError",
    "ReviewDecision",
    "ReviewDecisionStatus",
    "ReviewGate",
    "TeacherGuidanceSummary",
    "build_distillation_proposal",
    "normalize_teacher_guidance",
]
