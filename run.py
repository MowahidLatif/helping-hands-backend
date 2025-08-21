from app import create_app

app = create_app()

# poetry run flask:
#   --app app:create_app --debug run
#       ---OR---
#   poetry run flask --app app:create_app --debug run
# up:
# 	docker compose --env-file .env.docker up -d
# down:
# 	docker compose down
# logs:
# 	docker compose logs -f --tail=100
# nuke:
# 	docker compose down -v  # WARNING: deletes DB/Redis/S3 data
# Turn off containers:
#   docker compose --env-file .env.docker down
# Deletes all local data:
#   docker compose down -v
# Running the containers:
#   docker compose --env-file .env.docker up -d
#   docker compose --env-file .env.docker ps

# --- SCHEDULE ---

# Morning:
# open -a Docker
# docker compose --env-file .env.docker up -d
# docker compose --env-file .env.docker ps
# poetry run flask --app app:create_app --debug run

# Stopping:
# CTRL+C
# docker compose --env-file .env.docker down
