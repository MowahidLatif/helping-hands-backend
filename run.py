from app import create_app
from app.realtime import socketio, init_socketio
import os

app = create_app()
init_socketio(app)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    socketio.run(
        app,
        host="127.0.0.1",
        port=port,
        debug=False,
        use_reloader=False,
        log_output=True,
    )

# --- SCHEDULE ---

# Morning:
# open -a Docker
# docker compose --env-file .env.docker up -d
# docker compose --env-file .env.docker ps
# poetry run flask --app app:create_app --debug run

# Stopping:
# CTRL+C
# docker compose --env-file .env.docker down

# .env (CORS for your local frontends)
# SOCKETIO_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173

# New Process:

# Bring up local services
# open -a Docker
# docker compose --env-file .env.docker up -d

# Start your API + Socket.IO together (single process)
# PORT=5050 poetry run python run.py OR poetry run python run.py

# Stop the Python process with Ctrl+C in that terminal
# Then bring down containers:
# docker compose --env-file .env.docker down

# python -m http.server 8080
# http://127.0.0.1:8080/realtime_test.html
