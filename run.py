# run.py
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

# How to run app

# backend run command
# cd /Users/mowahidlatif/Code/donation-backend
# docker compose --env-file .env.docker up -d

# backend run command
# poetry install
# poetry run alembic upgrade head
# PORT=5050 poetry run python run.py

# frontend run command
# cd /Users/mowahidlatif/Code/frontend
# cp .env.example .env
# npm install
# npm run dev
