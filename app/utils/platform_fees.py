"""
Platform fee calculation for campaigns that reach their goal.

Tiered structure (applied to total_raised when goal is first reached):
  0 - 50,000         = 5%
  50,000 - 500,000   = 4%
  500,000 - 1,000,000 = 3%
  1,000,000+         = 2.5%

Fee is charged to the organization (campaign host), not the donor.
"""

from typing import Tuple

# (min_inclusive, max_exclusive, percent)
FEE_TIERS: list[Tuple[float, float, float]] = [
    (0, 50_000, 5.0),
    (50_000, 500_000, 4.0),
    (500_000, 1_000_000, 3.0),
    (1_000_000, float("inf"), 2.5),
]


def get_platform_fee_percent(total_raised_dollars: float) -> float:
    """
    Return the platform fee percentage for a given total raised.
    """
    total = max(0.0, float(total_raised_dollars))
    for min_val, max_val, pct in FEE_TIERS:
        if min_val <= total < max_val:
            return pct
    return FEE_TIERS[-1][2]  # fallback to highest tier


def calculate_platform_fee(total_raised_dollars: float) -> Tuple[float, float, int]:
    """
    Calculate platform fee for a campaign that reached its goal.

    Returns (fee_percent, fee_dollars, fee_cents).
    """
    total = max(0.0, float(total_raised_dollars))
    pct = get_platform_fee_percent(total)
    fee_dollars = round(total * (pct / 100.0), 2)
    fee_cents = int(round(fee_dollars * 100))
    return (pct, fee_dollars, fee_cents)
