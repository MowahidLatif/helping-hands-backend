"""Tests for donation fee accounting (v3 — no platform fee on donations)."""

from app.services.fee_policy_service import (
    FEE_OPTION_DONOR_PAYS,
    FEE_OPTION_PLATFORM_ABSORBS,
    FEE_POLICY_VERSION,
    build_donation_accounting,
)


def test_donor_pays_zero_platform_fee_full_net_to_org():
    accounting = build_donation_accounting(
        fee_option=FEE_OPTION_DONOR_PAYS,
        amount_cents=5_000,
        stripe_processing_fee_cents=175,
    )
    assert accounting.platform_fee_cents == 0
    assert accounting.platform_fee_percent == 0.0
    assert accounting.donor_fee_cents == 175
    assert accounting.platform_absorbed_fee_cents == 0
    assert accounting.net_to_org_cents == 5_000
    assert accounting.fee_policy_version == FEE_POLICY_VERSION


def test_platform_absorbs_deducts_stripe_fee_when_above_micro_threshold():
    accounting = build_donation_accounting(
        fee_option=FEE_OPTION_PLATFORM_ABSORBS,
        amount_cents=5_000,
        stripe_processing_fee_cents=175,
    )
    assert accounting.platform_fee_cents == 0
    assert accounting.platform_absorbed_fee_cents == 175
    assert accounting.donor_fee_cents == 0
    assert accounting.net_to_org_cents == 4_825


def test_platform_absorbs_micro_donation_passes_stripe_fee_to_donor():
    accounting = build_donation_accounting(
        fee_option=FEE_OPTION_PLATFORM_ABSORBS,
        amount_cents=500,
        stripe_processing_fee_cents=45,
    )
    assert accounting.platform_fee_cents == 0
    assert accounting.platform_absorbed_fee_cents == 0
    assert accounting.donor_fee_cents == 45
    assert accounting.net_to_org_cents == 500


def test_accounting_independent_of_tier():
    """Platform fee is always zero regardless of org/campaign tier."""
    for fee_option in (FEE_OPTION_DONOR_PAYS, FEE_OPTION_PLATFORM_ABSORBS):
        accounting = build_donation_accounting(
            fee_option=fee_option,
            amount_cents=10_000,
            stripe_processing_fee_cents=320,
        )
        assert accounting.platform_fee_cents == 0
        assert accounting.platform_fee_percent == 0.0
