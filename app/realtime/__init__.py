import os
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask import request
from flask_jwt_extended import decode_token

_raw = os.getenv("SOCKETIO_CORS_ORIGINS", "*").strip()
CORS_ORIGINS = "*" if _raw == "*" else [o.strip() for o in _raw.split(",") if o.strip()]
REQUIRE_AUTH = os.getenv("SOCKETIO_REQUIRE_AUTH", "0") == "1"

socketio = SocketIO(
    cors_allowed_origins=CORS_ORIGINS,
    async_mode="eventlet",
    logger=True,
    engineio_logger=True,
)


def init_socketio(app):
    socketio.init_app(app)

    def _validate_token(data) -> bool:
        if not REQUIRE_AUTH:
            return True
        token = (data or {}).get("token") if isinstance(data, dict) else None
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
        if not token:
            return False
        try:
            claims = decode_token(token)
            return bool(claims.get("sub")) and not bool(claims.get("pre_2fa"))
        except Exception:
            return False

    @socketio.on("connect")
    def handle_connect():
        print(
            "[socket] connect",
            "origin=",
            request.headers.get("Origin"),
            "ua=",
            request.headers.get("User-Agent"),
        )
        emit("connected", {"ok": True})

    @socketio.on("disconnect")
    def handle_disconnect():
        print("[socket] disconnect")

    @socketio.on("join_campaign")
    def on_join(data):
        if not _validate_token(data):
            emit("error", {"error": "unauthorized"})
            return
        cid = (data or {}).get("campaign_id")
        if not cid:
            emit("error", {"error": "campaign_id required"})
            return
        room = f"campaign:{cid}"
        join_room(room)
        emit("joined", {"room": room})

    @socketio.on("leave_campaign")
    def on_leave(data):
        if not _validate_token(data):
            emit("error", {"error": "unauthorized"})
            return
        cid = (data or {}).get("campaign_id")
        if not cid:
            return
        room = f"campaign:{cid}"
        leave_room(room)
        emit("left", {"room": room})
