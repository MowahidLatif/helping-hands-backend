# run.py
import os
import signal
import sys

from app import create_app
from app.realtime import socketio, init_socketio


def _graceful_shutdown(signum, frame):
    sys.exit(0)


signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)

app = create_app()
init_socketio(app)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    is_dev = os.getenv("FLASK_ENV") == "development"
    socketio.run(
        app,
        host="127.0.0.1",
        port=port,
        debug=is_dev,
        use_reloader=is_dev,
        log_output=True,
    )

# How to run app (development)
# cd /Users/mowahidlatif/Code/donation-backend
# docker compose --env-file .env.docker up -d
# poetry install
# poetry run alembic upgrade head
# PORT=5050 poetry run python run.py

# Production (Docker)
# docker build -t donation-backend .
# docker run -p 5050:5050 --env-file .env.production donation-backend
