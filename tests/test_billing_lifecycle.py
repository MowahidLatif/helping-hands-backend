"""Tests for tier change acknowledgment and delete-account billing cleanup."""

from unittest.mock import patch

from app.services.auth_service import delete_account
from app.utils.tier_features import check_tier_change_acknowledgment


@patch("app.utils.tier_features.list_in_flight_campaigns")
def test_check_tier_change_acknowledgment_returns_none_when_acknowledged(mock_list):
    mock_list.return_value = [{"id": "c1", "title": "Test"}]
    assert check_tier_change_acknowledgment("org1", True) is None
    mock_list.assert_not_called()


@patch("app.utils.tier_features.list_in_flight_campaigns")
def test_check_tier_change_acknowledgment_returns_none_without_campaigns(mock_list):
    mock_list.return_value = []
    assert check_tier_change_acknowledgment("org1", False) is None


@patch("app.utils.tier_features.list_in_flight_campaigns")
def test_check_tier_change_acknowledgment_requires_ack(mock_list):
    mock_list.return_value = [
        {
            "id": "c1",
            "title": "Spring Drive",
            "locked_tier": 2,
            "locked_tier_name": "Grow",
            "status": "active",
        }
    ]
    payload = check_tier_change_acknowledgment("org1", False)
    assert payload is not None
    assert payload["requires_acknowledgment"] is True
    assert len(payload["campaigns"]) == 1


@patch("app.services.auth_service.model_anonymize_user")
@patch("app.models.org_user.remove_user_from_org")
@patch("app.services.billing_service.cancel_subscription")
@patch("app.models.org.get_organization")
@patch("app.models.org_user.count_org_members_excluding")
@patch("app.models.org_user.count_org_owners")
@patch("app.models.org_user.get_primary_org_role")
@patch("app.services.auth_service.get_user_by_id")
def test_delete_account_owner_cancels_subscription(
    mock_get_user,
    mock_primary_org,
    mock_count_owners,
    mock_count_members,
    mock_get_org,
    mock_cancel,
    mock_remove,
    mock_anonymize,
):
    mock_get_user.return_value = {
        "id": "u1",
        "password_hash": "hash",
        "totp_enabled": False,
    }
    mock_primary_org.return_value = ("org1", "owner")
    mock_count_owners.return_value = 1
    mock_count_members.return_value = 0
    mock_get_org.return_value = {
        "id": "org1",
        "subscription_status": "active",
        "stripe_subscription_id": "sub_123",
    }
    mock_cancel.return_value = {"subscription_status": "canceled", "tier": 1}

    with patch("app.services.auth_service._verify_password", return_value=True):
        result = delete_account("u1", "password")

    assert result == {"success": True}
    mock_cancel.assert_called_once_with("org1")
    mock_remove.assert_called_once_with("org1", "u1")
    mock_anonymize.assert_called_once()


@patch("app.services.auth_service.get_user_by_id")
@patch("app.models.org_user.get_primary_org_role")
@patch("app.models.org_user.count_org_owners")
@patch("app.models.org_user.count_org_members_excluding")
def test_delete_account_blocks_sole_owner_with_other_members(
    mock_count_members,
    mock_count_owners,
    mock_primary_org,
    mock_get_user,
):
    mock_get_user.return_value = {
        "id": "u1",
        "password_hash": "hash",
        "totp_enabled": False,
    }
    mock_primary_org.return_value = ("org1", "owner")
    mock_count_owners.return_value = 1
    mock_count_members.return_value = 2

    with patch("app.services.auth_service._verify_password", return_value=True):
        result = delete_account("u1", "password")

    assert result.get("requires_ownership_transfer") is True
    assert "Transfer organization ownership" in result["error"]
