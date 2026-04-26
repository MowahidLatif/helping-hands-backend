from flask import Flask
from flask_jwt_extended import JWTManager

from app.routes import campaign_routes, org_routes

CAMP_ID = "00000000-0000-0000-0000-000000000001"
TASK_ID = "00000000-0000-0000-0000-000000000002"


def _make_app():
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = "test-secret"
    JWTManager(app)
    return app


def _unwrap_route(func):
    wrapped = func
    while hasattr(wrapped, "__wrapped__"):
        wrapped = wrapped.__wrapped__
    return wrapped


def test_create_task_requires_owner_or_admin(monkeypatch):
    app = _make_app()
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
        resp, status = route_fn(CAMP_ID)

    assert status == 403
    assert "owner/admin required" in resp.get_json()["error"]


def test_create_task_owner_success(monkeypatch):
    app = _make_app()
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
        lambda campaign_id, title, description=None, assignee_user_ids=None, status_id=None: {
            "id": TASK_ID,
            "campaign_id": campaign_id,
            "title": title,
            "description": description,
            "assignees": [
                {"user_id": uid, "name": None, "email": f"{uid}@example.com"}
                for uid in (assignee_user_ids or [])
            ],
            "status_id": status_id,
        },
    )

    with app.test_request_context(
        json={
            "title": "Task 1",
            "description": "Do something",
            "assignee_user_ids": ["member_1", "member_2"],
            "status_id": "status_1",
        }
    ):
        resp, status = route_fn(CAMP_ID)

    assert status == 201
    body = resp.get_json()
    assert body["title"] == "Task 1"
    assert len(body["assignees"]) == 2


def test_member_can_self_assign_unassigned_task(monkeypatch):
    app = _make_app()
    route_fn = _unwrap_route(campaign_routes.patch_campaign_task_route)

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign_task",
        lambda _task_id, _campaign_id: {
            "id": TASK_ID,
            "campaign_id": CAMP_ID,
            "assignees": [],
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "member_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )
    monkeypatch.setattr("app.routes.campaign_routes._can_view_task", lambda *_: True)
    monkeypatch.setattr(
        "app.routes.campaign_routes.update_campaign_task",
        lambda _task_id, _campaign_id, **updates: {
            "id": TASK_ID,
            "campaign_id": CAMP_ID,
            "assignees": [
                {"user_id": uid, "name": None, "email": None}
                for uid in (updates.get("assignee_user_ids") or [])
            ],
        },
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes._create_reassignment_system_comment",
        lambda **_kwargs: None,
    )

    with app.test_request_context(json={"assignee_user_ids": ["member_1"]}):
        resp, status = route_fn(CAMP_ID, TASK_ID)

    assert status == 200
    assert resp.get_json()["assignees"][0]["user_id"] == "member_1"


def test_member_cannot_self_assign_assigned_task(monkeypatch):
    app = _make_app()
    route_fn = _unwrap_route(campaign_routes.patch_campaign_task_route)

    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign",
        lambda _campaign_id: {"id": _campaign_id, "org_id": "org_1"},
    )
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_campaign_task",
        lambda _task_id, _campaign_id: {
            "id": TASK_ID,
            "campaign_id": CAMP_ID,
            "assignees": [{"user_id": "owner_1", "name": None, "email": None}],
        },
    )
    monkeypatch.setattr("app.routes.campaign_routes.get_jwt_identity", lambda: "member_1")
    monkeypatch.setattr(
        "app.routes.campaign_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "member",
    )
    monkeypatch.setattr("app.routes.campaign_routes._can_view_task", lambda *_: True)

    with app.test_request_context(json={"assignee_user_ids": ["member_1"]}):
        resp, status = route_fn(CAMP_ID, TASK_ID)

    assert status == 409
    assert "already assigned" in resp.get_json()["error"]


def test_org_tasks_endpoint_supports_campaign_filter(monkeypatch):
    app = _make_app()
    route_fn = _unwrap_route(org_routes.list_org_tasks)
    captured = {}

    def _fake_list_org_campaign_tasks(org_id, campaign_id=None, **_kwargs):
        captured["org_id"] = org_id
        captured["campaign_id"] = campaign_id
        return [
            {
                "id": TASK_ID,
                "campaign_id": CAMP_ID,
                "campaign_title": "Campaign 1",
                "title": "Task 1",
            }
        ]

    monkeypatch.setattr(
        "app.routes.org_routes.list_org_campaign_tasks",
        _fake_list_org_campaign_tasks,
    )
    monkeypatch.setattr("app.routes.org_routes.get_jwt_identity", lambda: "user_1")
    monkeypatch.setattr(
        "app.routes.org_routes.get_user_role_in_org",
        lambda *_args, **_kwargs: "owner",
    )

    with app.test_request_context(f"/api/orgs/org_1/tasks?campaign_id={CAMP_ID}"):
        resp, status = route_fn("org_1")

    assert status == 200
    assert captured == {"org_id": "org_1", "campaign_id": CAMP_ID}
    assert resp.get_json()[0]["campaign_title"] == "Campaign 1"
