"""Tests for billing-related Stripe webhook handling."""

import json
from unittest.mock import patch

from app.services.webhook_service import process_stripe_event


def _patch_common(monkeypatch):
    monkeypatch.setattr(
        "app.services.webhook_service.mark_event_processed",
        lambda *_args, **_kwargs: True,
    )


def test_checkout_session_completed_triggers_billing_handler(monkeypatch):
    _patch_common(monkeypatch)
    calls = {"checkout": 0}

    def _handle(session):
        calls["checkout"] += 1
        assert session["metadata"]["org_id"] == "org_1"

    monkeypatch.setattr(
        "app.services.billing_service.handle_checkout_session_completed",
        _handle,
    )

    payload = json.dumps(
        {
            "id": "evt_checkout_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_1",
                    "subscription": "sub_1",
                    "customer": "cus_1",
                    "metadata": {"org_id": "org_1", "tier": "2"},
                }
            },
        }
    ).encode("utf-8")

    status_code, body = process_stripe_event(payload, sig_header=None)
    assert status_code == 200
    assert body["ok"] is True
    assert calls["checkout"] == 1


def test_account_updated_syncs_connect(monkeypatch):
    _patch_common(monkeypatch)
    calls = {"sync": 0}

    monkeypatch.setattr(
        "app.services.connect_service.sync_connect_account_status",
        lambda account_id: calls.__setitem__("sync", calls["sync"] + 1),
    )

    payload = json.dumps(
        {
            "id": "evt_acct_1",
            "type": "account.updated",
            "data": {"object": {"id": "acct_123"}},
        }
    ).encode("utf-8")

    status_code, body = process_stripe_event(payload, sig_header=None)
    assert status_code == 200
    assert body["ok"] is True
    assert calls["sync"] == 1
