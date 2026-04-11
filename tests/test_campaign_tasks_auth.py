from flask import Flask

from app.routes import campaign_routes, org_routes


def _unwrap_route(func):
    wrapped = func
    while hasattr(wrapped, "__wrapped__"):
        wrapped = wrapped.__wrapped__
    return wrapped


def test_create_task_requires_owner_or_admin(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(campaign_routes.create_campaign_task_route)

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "user_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )

    with app.test_request_context(json={"title": "Task 1"}):
        resp, status = route_fn("camp_1")

    assert status == 403
    assert "owner/admin required" in resp.get_json()["error"]


def test_create_task_owner_success(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(campaign_routes.create_campaign_task_route)

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "owner_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda user_id, _org_id: "owner" if user_id == "owner_1" else "member",
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_task_status",
        lambda _status_id, _org_id: {"id": _status_id},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.create_campaign_task",
        lambda campaign_id, title, description=None, assignee_user_id=None, status_id=None: {
            "id": "task_1",
            "campaign_id": campaign_id,
            "title": title,
            "description": description,
            "assignee_user_id": assignee_user_id,
            "status_id": status_id,
        },
    )

    with app.test_request_context(
        json={
            "title": "Task 1",
            "description": "Do something",
            "assignee_user_id": "member_1",
            "status_id": "status_1",
        }
    ):
        resp, status = route_fn("camp_1")

    assert status == 201
    body = resp.get_json()
    assert body["title"] == "Task 1"
    assert body["assignee_user_id"] == "member_1"


def test_member_can_self_assign_unassigned_task(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(campaign_routes.patch_campaign_task_route)

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign_task",
        lambda _task_id, _campaign_id: {
            "id": "task_1",
            "campaign_id": "camp_1",
            "assignee_user_id": None,
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "member_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.update_campaign_task",
        lambda _task_id, _campaign_id, **updates: {
            "id": "task_1",
            "campaign_id": "camp_1",
            "assignee_user_id": updates.get("assignee_user_id"),
        },
    )

    with app.test_request_context(json={"assignee_user_id": "member_1"}):
        resp, status = route_fn("camp_1", "task_1")

    assert status == 200
    assert resp.get_json()["assignee_user_id"] == "member_1"


def test_member_cannot_self_assign_assigned_task(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(campaign_routes.patch_campaign_task_route)

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign_task",
        lambda _task_id, _campaign_id: {
            "id": "task_1",
            "campaign_id": "camp_1",
            "assignee_user_id": "owner_1",
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "member_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )

    with app.test_request_context(json={"assignee_user_id": "member_1"}):
        resp, status = route_fn("camp_1", "task_1")

    assert status == 409
    assert "already assigned" in resp.get_json()["error"]


def test_org_tasks_endpoint_supports_campaign_filter(monkeypatch):
    app = Flask(__name__)
    route_fn = _unwrap_route(org_routes.list_org_tasks)
    captured = {}

    def _fake_list_org_campaign_tasks(org_id, campaign_id=None):
        captured["org_id"] = org_id
        captured["campaign_id"] = campaign_id
        return [
            {
                "id": "task_1",
                "campaign_id": "camp_1",
                "campaign_title": "Campaign 1",
                "title": "Task 1",
            }
        ]

    monkeypatch.setattr(
        "app.routes.org_routes.list_org_campaign_tasks",
        _fake_list_org_campaign_tasks,
    )

    with app.test_request_context("/api/orgs/org_1/tasks?campaign_id=camp_1"):
        resp, status = route_fn("org_1")

    assert status == 200
    assert captured == {"org_id": "org_1", "campaign_id": "camp_1"}
    assert resp.get_json()[0]["campaign_title"] == "Campaign 1"
