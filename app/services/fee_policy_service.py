from __future__ import annotations

import os
from dataclasses import dataclass

FEE_POLICY_VERSION = "v3"
FEE_OPTION_DONOR_PAYS = "donor_pays"
FEE_OPTION_PLATFORM_ABSORBS = "platform_absorbs"
VALID_FEE_OPTIONS = {FEE_OPTION_DONOR_PAYS, FEE_OPTION_PLATFORM_ABSORBS}

MICRO_DONATION_THRESHOLD_CENTS = 1_000

_STRIPE_PCT_DEFAULT = float(os.getenv("STRIPE_PROCESSING_PERCENT", "2.9") or "2.9")
_STRIPE_FIXED_DEFAULT = int(os.getenv("STRIPE_PROCESSING_FIXED_CENTS", "30") or "30")


@dataclass(frozen=True)
class DonationAccounting:
    fee_option: str
    fee_policy_version: str
    stripe_processing_fee_cents: int
    platform_fee_percent: float
    platform_fee_cents: int
    donor_fee_cents: int
    platform_absorbed_fee_cents: int
    net_to_org_cents: int


def normalize_fee_option(raw: str | None) -> str:
    value = (raw or FEE_OPTION_DONOR_PAYS).strip().lower()
    if value not in VALID_FEE_OPTIONS:
        return FEE_OPTION_DONOR_PAYS
    return value


def estimate_stripe_processing_fee_cents(amount_cents: int) -> int:
    gross = max(0, int(amount_cents))
    return int(round(gross * (_STRIPE_PCT_DEFAULT / 100.0))) + _STRIPE_FIXED_DEFAULT


def compute_gross_charge_for_donor_cover(amount_cents: int) -> int:
    """
    Compute an estimated gross charge so that net after Stripe fees
    is at least the intended base donation amount.
    """
    base = max(0, int(amount_cents))
    if base <= 0:
        return 0
    pct = max(0.0, min(_STRIPE_PCT_DEFAULT / 100.0, 0.99))
    gross = int(round((base + _STRIPE_FIXED_DEFAULT) / (1.0 - pct)))
    return max(base, gross)


def build_donation_accounting(
    *,
    fee_option: str,
    amount_cents: int,
    stripe_processing_fee_cents: int,
) -> DonationAccounting:
    gross = max(0, int(amount_cents))
    stripe_fee = max(0, int(stripe_processing_fee_cents))
    option = normalize_fee_option(fee_option)
    platform_fee_percent = 0.0
    platform_fee_cents = 0

    donor_fee_cents = 0
    platform_absorbed_fee_cents = 0
    if option == FEE_OPTION_DONOR_PAYS:
        donor_fee_cents = stripe_fee
    else:
        if gross >= MICRO_DONATION_THRESHOLD_CENTS:
            platform_absorbed_fee_cents = stripe_fee
        else:
            donor_fee_cents = stripe_fee

    net_to_org_cents = gross - platform_absorbed_fee_cents
    if net_to_org_cents < 0:
        net_to_org_cents = 0

    return DonationAccounting(
        fee_option=option,
        fee_policy_version=FEE_POLICY_VERSION,
        stripe_processing_fee_cents=stripe_fee,
        platform_fee_percent=platform_fee_percent,
        platform_fee_cents=platform_fee_cents,
        donor_fee_cents=donor_fee_cents,
        platform_absorbed_fee_cents=platform_absorbed_fee_cents,
        net_to_org_cents=net_to_org_cents,
    )
