"""
Platform fee helpers. Fee percentage is determined by the org's tier, not campaign volume.

Tier 1 (Starter)  = 3%
Tier 2 (Grow)     = 4%
Tier 3 (Scale)    = 5%

Early campaign cancellation (any tier) = flat 5%.
"""

from typing import Tuple

CANCELLATION_FEE_PERCENT = 5.0


def get_platform_fee_percent(org_tier: int) -> float:
    """Return the platform fee percentage for the given org tier."""
    from app.utils.tier_features import TIER_LIMITS
    tier = int(org_tier) if org_tier in (1, 2, 3) else 1
    return TIER_LIMITS[tier]["platform_fee_percent"]


def calculate_platform_fee(total_raised_dollars: float, org_tier: int = 1) -> Tuple[float, float, int]:
    """
    Calculate platform fee for a campaign payout.

    Returns (fee_percent, fee_dollars, fee_cents).
    """
    total = max(0.0, float(total_raised_dollars))
    pct = get_platform_fee_percent(org_tier)
    fee_dollars = round(total * (pct / 100.0), 2)
    fee_cents = int(round(fee_dollars * 100))
    return (pct, fee_dollars, fee_cents)


def calculate_cancellation_fee(total_raised_dollars: float) -> Tuple[float, float, int]:
    """
    Calculate the 5% early cancellation fee.

    Returns (fee_percent, fee_dollars, fee_cents).
    """
    total = max(0.0, float(total_raised_dollars))
    pct = CANCELLATION_FEE_PERCENT
    fee_dollars = round(total * (pct / 100.0), 2)
    fee_cents = int(round(fee_dollars * 100))
    return (pct, fee_dollars, fee_cents)
