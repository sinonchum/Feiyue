"""Creative candidate schemas."""

from feiyue_core.creative.brief import CreativeBrief
from feiyue_core.creative.critique import CreativeCritique, CreativeCritiqueRecommendation
from feiyue_core.creative.selection import UserSelectionFeedback, UserSelectionStatus
from feiyue_core.creative.variant import CreativeVariant, CreativeVariantType

__all__ = [
    "CreativeBrief",
    "CreativeCritique",
    "CreativeCritiqueRecommendation",
    "CreativeVariant",
    "CreativeVariantType",
    "UserSelectionFeedback",
    "UserSelectionStatus",
]
