import os
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask import request  # for debugging

# Read env; keep "*" as a literal wildcard
_raw = os.getenv("SOCKETIO_CORS_ORIGINS", "*").strip()
CORS_ORIGINS = "*" if _raw == "*" else [o.strip() for o in _raw.split(",") if o.strip()]

# Turn on low-noise logs to see handshakes (helpful while debugging)
socketio = SocketIO(
    cors_allowed_origins=CORS_ORIGINS,
    async_mode="eventlet",
    logger=True,
    engineio_logger=True,
)


def init_socketio(app):
    socketio.init_app(app)

    @socketio.on("connect")
    def handle_connect():
        # debug: see origin & transport
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
        cid = (data or {}).get("campaign_id")
        if not cid:
            emit("error", {"error": "campaign_id required"})
            return
        room = f"campaign:{cid}"
        join_room(room)
        emit("joined", {"room": room})

    @socketio.on("leave_campaign")
    def on_leave(data):
        cid = (data or {}).get("campaign_id")
        if not cid:
            return
        room = f"campaign:{cid}"
        leave_room(room)
        emit("left", {"room": room})


# import os
# from flask_socketio import SocketIO, join_room, leave_room, emit

# # Allow all in dev unless specified
# CORS_ORIGINS = os.getenv("SOCKETIO_CORS_ORIGINS", "*")
# CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS.split(",")] if CORS_ORIGINS else "*"

# # async_mode="eventlet" so we can run socketio.run(...) with eventlet
# socketio = SocketIO(cors_allowed_origins=CORS_ORIGINS, async_mode="eventlet")

# def init_socketio(app):
#     socketio.init_app(app)

#     @socketio.on("connect")
#     def handle_connect():
#         emit("connected", {"ok": True})

#     @socketio.on("disconnect")
#     def handle_disconnect():
#         # noop, but handy for logging
#         pass

#     @socketio.on("join_campaign")
#     def on_join(data):
#         cid = (data or {}).get("campaign_id")
#         if not cid:
#             emit("error", {"error": "campaign_id required"})
#             return
#         room = f"campaign:{cid}"
#         join_room(room)
#         emit("joined", {"room": room})

#     @socketio.on("leave_campaign")
#     def on_leave(data):
#         cid = (data or {}).get("campaign_id")
#         if not cid:
#             return
#         room = f"campaign:{cid}"
#         leave_room(room)
#         emit("left", {"room": room})
