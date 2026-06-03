"""Tests for Stripe Billing service helpers."""

from unittest.mock import MagicMock, patch

import app.services.billing_service as billing_mod
from app.services.billing_service import (
    apply_subscription_state,
    billing_required,
    org_has_active_billing,
    price_id_to_tier,
    tier_to_price_id,
)


def test_tier_price_mapping():
    with patch.object(billing_mod, "STRIPE_PRICE_STARTER", "price_starter"), patch.object(
        billing_mod, "STRIPE_PRICE_GROW", "price_grow"
    ), patch.object(billing_mod, "STRIPE_PRICE_SCALE", "price_scale"):
        assert tier_to_price_id(1) == "price_starter"
        assert price_id_to_tier("price_grow") == 2


def test_org_has_active_billing_legacy():
    assert org_has_active_billing({"subscription_status": "legacy"}) is True


def test_org_has_active_billing_none():
    assert org_has_active_billing({"subscription_status": "none"}) is False
    assert billing_required({"subscription_status": "none"}) is True


@patch("app.services.billing_service.update_active_campaigns_locked_tier")
@patch("app.services.billing_service.update_org_subscription")
@patch("app.services.billing_service.get_organization")
def test_apply_subscription_state_active(mock_get_org, mock_update_sub, mock_update_locked):
    mock_get_org.return_value = {"id": "org1", "tier": 1}
    mock_update_sub.return_value = {"id": "org1", "tier": 2}

    sub = MagicMock()
    sub.id = "sub_123"
    sub.status = "active"
    sub.metadata = {"tier": "2"}
    sub.current_period_end = 1_700_000_000
    sub.items = MagicMock(data=[])

    apply_subscription_state("org1", sub)

    mock_update_sub.assert_called_once()
    mock_update_locked.assert_called_once_with("org1", 2)


@patch("app.services.billing_service.update_org_subscription")
@patch("app.services.billing_service.get_organization")
def test_apply_subscription_state_canceled_downgrades(mock_get_org, mock_update_sub):
    mock_get_org.return_value = {"id": "org1", "tier": 3, "pending_tier": None}
    mock_update_sub.return_value = {"id": "org1", "tier": 1}

    sub = MagicMock()
    sub.id = "sub_123"
    sub.status = "canceled"
    sub.metadata = {"tier": "3"}
    sub.current_period_end = None
    sub.items = MagicMock(data=[])

    apply_subscription_state("org1", sub)

    call_kwargs = mock_update_sub.call_args.kwargs
    assert call_kwargs["tier"] == 1
    assert call_kwargs["subscription_status"] == "canceled"
