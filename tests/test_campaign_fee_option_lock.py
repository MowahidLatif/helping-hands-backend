from flask import Flask

from app.models.campaign import is_fee_option_locked
from app.routes import campaign_routes


def _unwrap_route(func):
    wrapped = func
    while hasattr(wrapped, "__wrapped__"):
        wrapped = wrapped.__wrapped__
    return wrapped


def test_is_fee_option_locked_helper():
    assert is_fee_option_locked("draft") is False
    assert is_fee_option_locked("active") is True
    assert is_fee_option_locked("paused") is True
    assert is_fee_option_locked("completed") is True


def test_patch_blocks_fee_option_change_after_publish(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {
            "id": "camp_active",
            "org_id": "org_1",
            "status": "active",
            "fee_option": "donor_pays",
            "fee_policy_version": "v1",
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "user_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "owner",
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.user_has_permission",
        lambda *_args, **_kwargs: True,
    )

    route_fn = _unwrap_route(campaign_routes.patch)
    with app.test_request_context(json={"fee_option": "platform_absorbs"}):
        resp, status = route_fn("camp_active")

    assert status == 409
    assert "published" in resp.get_json()["error"]


def test_patch_blocks_fee_option_change_when_completed(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {
            "id": "camp_done",
            "org_id": "org_1",
            "status": "completed",
            "fee_option": "donor_pays",
            "fee_policy_version": "v1",
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "user_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "owner",
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.user_has_permission",
        lambda *_args, **_kwargs: True,
    )

    route_fn = _unwrap_route(campaign_routes.patch)
    with app.test_request_context(json={"fee_option": "platform_absorbs"}):
        resp, status = route_fn("camp_done")

    assert status == 409
    assert "completion" in resp.get_json()["error"]


def test_patch_allows_draft_fee_option_and_snapshots_policy_on_publish(monkeypatch):
    app = Flask(__name__)
    captured = {}

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {
            "id": "camp_draft",
            "org_id": "org_1",
            "status": "draft",
            "fee_option": "donor_pays",
            "fee_policy_version": "v1",
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "user_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "owner",
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.user_has_permission",
        lambda *_args, **_kwargs: True,
    )

    def _fake_update_campaign(_campaign_id, **updates):
        captured.update(updates)
        return {
            "id": "camp_draft",
            "org_id": "org_1",
            "status": updates.get("status", "draft"),
            "fee_option": updates.get("fee_option", "donor_pays"),
            "fee_policy_version": updates.get("fee_policy_version", "v1"),
        }

    monkeypatch.setattr(
        "app.routes.campaign_routes.update_campaign", _fake_update_campaign
    )

    route_fn = _unwrap_route(campaign_routes.patch)
    with app.test_request_context(
        json={"fee_option": "platform_absorbs", "status": "active"}
    ):
        resp, status = route_fn("camp_draft")

    assert status == 200
    assert captured["fee_option"] == "platform_absorbs"
    assert captured["status"] == "active"
    assert captured["fee_policy_version"] == "v1"
    body = resp.get_json()
    assert body["fee_option"] == "platform_absorbs"
