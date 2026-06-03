"""Tests for free trial and monthly/annual billing."""

from unittest.mock import MagicMock, patch

import app.services.billing_service as billing_mod
from app.services.billing_service import (
    apply_subscription_state,
    create_subscription_checkout,
    is_trial_eligible,
    tier_to_price_id,
    _map_subscription_status,
)


def test_map_subscription_status_trialing():
    assert _map_subscription_status("trialing") == "trialing"
    assert _map_subscription_status("active") == "active"


def test_tier_price_mapping_monthly_annual():
    with patch.object(billing_mod, "STRIPE_PRICE_STARTER_MONTHLY", "price_s_m"), patch.object(
        billing_mod, "STRIPE_PRICE_STARTER_ANNUAL", "price_s_a"
    ), patch.object(billing_mod, "STRIPE_PRICE_GROW_MONTHLY", "price_g_m"), patch.object(
        billing_mod, "STRIPE_PRICE_GROW_ANNUAL", "price_g_a"
    ), patch.object(billing_mod, "STRIPE_PRICE_SCALE_MONTHLY", "price_sc_m"), patch.object(
        billing_mod, "STRIPE_PRICE_SCALE_ANNUAL", "price_sc_a"
    ):
        assert tier_to_price_id(1, "monthly") == "price_s_m"
        assert tier_to_price_id(2, "annual") == "price_g_a"


def test_is_trial_eligible_only_none_status():
    assert is_trial_eligible({"subscription_status": "none"}) is True
    assert is_trial_eligible({"subscription_status": "canceled"}) is False
    assert is_trial_eligible({"subscription_status": "active"}) is False


@patch("app.services.billing_service.update_active_campaigns_locked_tier")
@patch("app.services.billing_service.update_org_subscription")
@patch("app.services.billing_service.get_organization")
def test_apply_subscription_state_trialing(mock_get_org, mock_update_sub, mock_update_locked):
    mock_get_org.return_value = {"id": "org1", "tier": 1, "billing_interval": "monthly"}
    mock_update_sub.return_value = {"id": "org1", "tier": 2, "subscription_status": "trialing"}

    sub = MagicMock()
    sub.id = "sub_123"
    sub.status = "trialing"
    sub.metadata = {"tier": "2", "interval": "monthly"}
    sub.trial_end = 1_800_000_000
    sub.current_period_end = 1_800_000_000
    sub.cancel_at_period_end = False
    sub.cancel_at = None
    sub.items = MagicMock(data=[])

    apply_subscription_state("org1", sub)

    call_kwargs = mock_update_sub.call_args.kwargs
    assert call_kwargs["subscription_status"] == "trialing"
    assert call_kwargs["tier"] == 2
    mock_update_locked.assert_called_once_with("org1", 2)


@patch("app.services.billing_service.stripe.checkout.Session.create")
@patch("app.services.billing_service.setup_billing")
@patch("app.services.billing_service.update_org_billing")
@patch("app.services.billing_service.get_organization")
def test_checkout_includes_trial_for_new_org(
    mock_get_org, mock_update_billing, mock_setup, mock_session_create
):
    mock_get_org.return_value = {
        "id": "org1",
        "name": "Org",
        "subscription_status": "none",
    }
    mock_setup.return_value = {"customer_id": "cus_1", "connect_account_id": "acct_1"}
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/x", id="cs_1")

    with patch.object(billing_mod, "STRIPE_SECRET_KEY", "sk_test"), patch.object(
        billing_mod, "STRIPE_BILLING_SUCCESS_URL", "http://ok"
    ), patch.object(billing_mod, "STRIPE_BILLING_CANCEL_URL", "http://cancel"), patch.object(
        billing_mod, "STRIPE_PRICE_GROW_MONTHLY", "price_grow_m"
    ), patch.object(billing_mod, "STRIPE_TRIAL_DAYS", 7):
        result = create_subscription_checkout("org1", 2, "o@example.com", interval="monthly")

    assert result.get("trial_eligible") is True
    assert result.get("trial_days") == 7
    sub_data = mock_session_create.call_args.kwargs["subscription_data"]
    assert sub_data["trial_period_days"] == 7
    assert mock_session_create.call_args.kwargs["payment_method_collection"] == "always"


@patch("app.services.billing_service.stripe.checkout.Session.create")
@patch("app.services.billing_service.setup_billing")
@patch("app.services.billing_service.update_org_billing")
@patch("app.services.billing_service.get_organization")
def test_checkout_no_trial_for_resubscribe(
    mock_get_org, mock_update_billing, mock_setup, mock_session_create
):
    mock_get_org.return_value = {
        "id": "org1",
        "name": "Org",
        "subscription_status": "canceled",
        "stripe_subscription_id": "sub_old",
    }
    mock_setup.return_value = {"customer_id": "cus_1", "connect_account_id": "acct_1"}
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/x", id="cs_1")

    with patch.object(billing_mod, "STRIPE_SECRET_KEY", "sk_test"), patch.object(
        billing_mod, "STRIPE_BILLING_SUCCESS_URL", "http://ok"
    ), patch.object(billing_mod, "STRIPE_BILLING_CANCEL_URL", "http://cancel"), patch.object(
        billing_mod, "STRIPE_PRICE_GROW_MONTHLY", "price_grow_m"
    ), patch.object(billing_mod, "STRIPE_TRIAL_DAYS", 7):
        create_subscription_checkout("org1", 2, "o@example.com", interval="monthly")

    sub_data = mock_session_create.call_args.kwargs["subscription_data"]
    assert "trial_period_days" not in sub_data
