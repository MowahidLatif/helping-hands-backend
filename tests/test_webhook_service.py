import json

from app.services.webhook_service import process_stripe_event


def _patch_common(monkeypatch):
    monkeypatch.setattr(
        "app.services.webhook_service.mark_event_processed",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.webhook_service.invalidate_public_campaign_cache",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.webhook_service.recompute_total_raised",
        lambda *_args, **_kwargs: {"total_raised": 12.34},
    )
    monkeypatch.setattr(
        "app.services.webhook_service.record_platform_fee_if_goal_reached",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.webhook_service.r",
        lambda: type("FakeRedis", (), {"delete": lambda *_args, **_kwargs: None})(),
    )
    monkeypatch.setattr(
        "app.services.webhook_service.socketio",
        type("FakeSocket", (), {"emit": lambda *_args, **_kwargs: None})(),
    )
    monkeypatch.setattr(
        "app.services.webhook_service.enqueue_receipt_email",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.webhook_service.get_campaign",
        lambda _campaign_id: {
            "id": _campaign_id,
            "status": "active",
            "fee_option": "donor_pays",
            "fee_policy_version": "v1",
            "total_raised": 0,
        },
    )
    monkeypatch.setattr(
        "app.services.webhook_service.update_donation_accounting",
        lambda *_args, **_kwargs: None,
    )


def test_payment_intent_succeeded_updates_status(monkeypatch):
    _patch_common(monkeypatch)
    calls = {"status_by_pi": None, "status_by_id": None}

    monkeypatch.setattr(
        "app.services.webhook_service.get_donation_by_pi",
        lambda pi_id: {
            "id": "don_1",
            "campaign_id": "camp_1",
            "amount_cents": 2500,
            "currency": "usd",
            "donor_email": "a@example.com",
            "stripe_payment_intent_id": pi_id,
        },
    )
    monkeypatch.setattr(
        "app.services.webhook_service.get_donation",
        lambda donation_id: {
            "id": donation_id,
            "campaign_id": "camp_1",
            "stripe_payment_intent_id": None,
        },
    )
    monkeypatch.setattr(
        "app.services.webhook_service.set_status_by_pi",
        lambda _pi, status: calls.__setitem__("status_by_pi", status),
    )
    monkeypatch.setattr(
        "app.services.webhook_service.set_status_by_id",
        lambda _donation_id, status: calls.__setitem__("status_by_id", status),
    )
    monkeypatch.setattr(
        "app.services.webhook_service.attach_pi_to_donation",
        lambda *_args, **_kwargs: None,
    )

    payload = json.dumps(
        {
            "id": "evt_1",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "metadata": {"donation_id": "don_1", "campaign_id": "camp_1"},
                }
            },
        }
    ).encode("utf-8")

    status_code, body = process_stripe_event(payload, sig_header=None)

    assert status_code == 200
    assert body["ok"] is True
    assert "succeeded" in {calls["status_by_pi"], calls["status_by_id"]}


def test_charge_refunded_marks_donation_refunded(monkeypatch):
    _patch_common(monkeypatch)
    calls = {"status": None}

    monkeypatch.setattr(
        "app.services.webhook_service.get_donation_by_pi",
        lambda _pi_id: {
            "id": "don_2",
            "campaign_id": "camp_2",
            "amount_cents": 5000,
            "currency": "usd",
            "donor_email": "b@example.com",
            "stripe_payment_intent_id": "pi_456",
        },
    )
    monkeypatch.setattr(
        "app.services.webhook_service.get_donation",
        lambda donation_id: {"id": donation_id, "campaign_id": "camp_2"},
    )
    monkeypatch.setattr(
        "app.services.webhook_service.set_status_by_pi",
        lambda _pi, status: calls.__setitem__("status", status),
    )
    monkeypatch.setattr(
        "app.services.webhook_service.set_status_by_id",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.webhook_service.attach_pi_to_donation",
        lambda *_args, **_kwargs: None,
    )

    payload = json.dumps(
        {
            "id": "evt_2",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_123",
                    "payment_intent": "pi_456",
                    "metadata": {"campaign_id": "camp_2"},
                }
            },
        }
    ).encode("utf-8")

    status_code, body = process_stripe_event(payload, sig_header=None)

    assert status_code == 200
    assert body["ok"] is True
    assert calls["status"] == "refunded"
