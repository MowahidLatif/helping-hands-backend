from flask import Flask

from app.routes import campaign_routes

CAMP_ID = "00000000-0000-0000-0000-000000000001"
TASK_ID = "00000000-0000-0000-0000-000000000002"


def _unwrap_route(func):
    wrapped = func
    while hasattr(wrapped, "__wrapped__"):
        wrapped = wrapped.__wrapped__
    return wrapped


def test_non_assignee_cannot_view_task_comments(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(campaign_routes.list_task_comments_route)

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign_task",
        lambda _task_id, _campaign_id: {
            "id": TASK_ID,
            "assignees": [{"user_id": "member_2"}],
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "member_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )

    with app.test_request_context():
        resp, status = route_fn(CAMP_ID, TASK_ID)

    assert status == 403
    assert resp.get_json()["error"] == "forbidden"


def test_status_change_creates_system_comment(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(campaign_routes.patch_campaign_task_route)
    captured = {"status_comment_called": False}

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign_task",
        lambda _task_id, _campaign_id: {
            "id": TASK_ID,
            "status_id": "s_old",
            "assignees": [{"user_id": "member_1"}],
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "member_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_task_status",
        lambda status_id, _org_id: {"id": status_id, "name": status_id},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.update_campaign_task",
        lambda *_args, **_kwargs: {
            "id": TASK_ID,
            "status_id": "s_new",
            "assignees": [{"user_id": "member_1"}],
        },
    )

    def _fake_status_comment(**_kwargs):
        captured["status_comment_called"] = True

    monkeypatch.setattr(
        "app.routes.campaign_routes._create_status_change_system_comment",
        _fake_status_comment,
    )

    with app.test_request_context(json={"status_id": "s_new"}):
        _resp, status = route_fn(CAMP_ID, TASK_ID)

    assert status == 200
    assert captured["status_comment_called"] is True


def test_blocked_comment_creates_notification_intents(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(campaign_routes.create_task_comment_route)
    captured = {"recipients": []}

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign_task",
        lambda _task_id, _campaign_id: {"id": TASK_ID, "assignees": [{"user_id": "member_1"}]},
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "member_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.create_task_comment",
        lambda **_kwargs: {"id": "comment_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.list_org_user_ids_by_roles",
        lambda *_args, **_kwargs: ["owner_1", "admin_1", "member_1"],
    )

    def _fake_create_notification_intents(**kwargs):
        captured["recipients"] = kwargs.get("recipient_user_ids", [])

    monkeypatch.setattr(
        "app.routes.campaign_routes.create_notification_intents",
        _fake_create_notification_intents,
    )

    with app.test_request_context(json={"comment_type": "blocked", "body": "Cannot proceed"}):
        _resp, status = route_fn(CAMP_ID, TASK_ID)

    assert status == 201
    assert captured["recipients"] == ["owner_1", "admin_1"]
